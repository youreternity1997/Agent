from sqlalchemy import select

from app.core.llm import embed
from app.db.database import AsyncSessionLocal
from app.db.models import KBDocument


async def rag_search(query: str, top_k: int = 4) -> str:
    """Semantic search over the pgvector knowledge base of GIGABYTE product docs."""
    try:
        query_vector = await embed(query)
    except Exception as exc:  # noqa: BLE001
        return f"[rag_search 工具錯誤] 無法產生查詢向量：{exc}"

    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                KBDocument,
                KBDocument.embedding.cosine_distance(query_vector).label("distance"),
            )
            .order_by(KBDocument.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        try:
            rows = (await session.execute(stmt)).all()
        except Exception as exc:  # noqa: BLE001
            return f"[rag_search 工具錯誤] 資料庫查詢失敗：{exc}"

    if not rows:
        return "知識庫中沒有找到相關文件（資料庫可能尚未執行 seed_data.py 灌入資料）。"

    lines = [f"RAG 向量檢索「{query}」的相關文件（依相似度排序）："]
    for i, (doc, distance) in enumerate(rows, start=1):
        similarity = max(0.0, 1 - float(distance))
        lines.append(
            f"{i}. [{doc.title}] (相似度 {similarity:.2f})\n{doc.content.strip()}"
        )
    return "\n\n".join(lines)
