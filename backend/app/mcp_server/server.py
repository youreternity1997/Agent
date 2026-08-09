"""MCP tool server for the GIGABYTE AI Agent.

Exposes three tools over the Model Context Protocol (stdio transport):
  - web_search: live internet search (Tavily)
  - rag_search: semantic vector search over the pgvector knowledge base
  - db_query:   structured/exact lookup against the motherboards table

Run standalone for debugging:
    python -m app.mcp_server.server
The FastAPI backend normally launches this as a subprocess via mcp_client/client.py.
"""

import sys
from pathlib import Path

# Allow running as a plain script (python app/mcp_server/server.py) as well as -m.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.mcp_server.tools.db_query import db_query as _db_query  # noqa: E402
from app.mcp_server.tools.rag_search import rag_search as _rag_search  # noqa: E402
from app.mcp_server.tools.web_search import web_search as _web_search  # noqa: E402

mcp = FastMCP("gigabyte-tools")


@mcp.tool()
async def web_search(query: str) -> str:
    """在網路上搜尋即時/當下資訊，回傳搜尋結果摘要。適用於任何你自己知識可能過時或不知道的
    即時性問題，例如：最新價格、新聞、評測、目前日期時間、匯率、庫存狀況等，不限於這幾種類型。"""
    return await _web_search(query)


@mcp.tool()
async def rag_search(query: str, top_k: int = 4) -> str:
    """對技嘉主機板知識庫做語意向量檢索 (RAG)，適合模糊、描述性的規格/特色問題。"""
    return await _rag_search(query, top_k=top_k)


@mcp.tool()
async def db_query(keyword: str, limit: int = 5) -> str:
    """直接查詢主機板資料庫（依型號/系列/腳位/晶片組關鍵字），適合明確指定型號的精確查詢。"""
    return await _db_query(keyword, limit=limit)


if __name__ == "__main__":
    mcp.run(transport="stdio")
