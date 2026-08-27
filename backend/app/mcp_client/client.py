"""MCP client that talks to app.mcp_server.server over stdio.

Each chat request opens its own short-lived MCP session (simple + process-isolated,
appropriate for a reference/demo project). The ReAct agent uses this to discover
available tools (for the /api/tools endpoint) and to invoke whichever tools the
user selected via the frontend checkboxes.
"""

import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import get_settings

settings = get_settings()

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp_server.server"],
    cwd=str(settings.backend_root),
    # mcp's stdio_client only forwards a small safe-var whitelist when env=None,
    # which drops OLLAMA_BASE_URL / DATABASE_URL etc. set via docker-compose -
    # the subprocess then falls back to Settings' localhost defaults and can't
    # reach the ollama/db containers. This is a trusted in-process subprocess,
    # so inherit the full environment instead.
    env=dict(os.environ),
)


@asynccontextmanager
async def mcp_session():
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_mcp_tools() -> list[dict]:
    """Return [{id, name, description}] for every tool the MCP server exposes."""
    async with mcp_session() as session:
        result = await session.list_tools()
    return [
        {"id": tool.name, "name": tool.name, "description": tool.description or ""}
        for tool in result.tools
    ]


async def call_mcp_tool(session: ClientSession, name: str, arguments: dict) -> str:
    result = await session.call_tool(name, arguments)
    if result.isError:
        text = "\n".join(getattr(c, "text", str(c)) for c in result.content)
        return f"[工具執行錯誤] {text}"
    parts = []
    for content in result.content:
        text = getattr(content, "text", None)
        parts.append(text if text is not None else str(content))
    return "\n".join(parts) if parts else "(工具沒有回傳內容)"
