from sqlalchemy import select

from app.core.config import get_settings
from app.core.llm import embed
from app.core.rerank import rerank
from app.db.database import AsyncSessionLocal
from app.db.models import KBDocument

settings = get_settings()


async def rag_search(query: str, top_k: int = 4) -> str:
    """Semantic search over the pgvector knowledge base of GIGABYTE product docs,
    narrowed down with a cross-encoder reranker for better precision."""
    try:
        query_vector = await embed(query)
    except Exception as exc:  # noqa: BLE001
        return f"[rag_search 工具錯誤] 無法產生查詢向量：{exc}"

    candidate_k = max(top_k, settings.rerank_candidate_k) if settings.rerank_enabled else top_k

    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                KBDocument,
                KBDocument.embedding.cosine_distance(query_vector).label("distance"),
            )
            .order_by(KBDocument.embedding.cosine_distance(query_vector))
            .limit(candidate_k)
        )
        try:
            rows = (await session.execute(stmt)).all()
        except Exception as exc:  # noqa: BLE001
            return f"[rag_search 工具錯誤] 資料庫查詢失敗：{exc}"

    if not rows:
        return "知識庫中沒有找到相關文件（資料庫可能尚未執行 seed_data.py 灌入資料）。"

    rerank_note = ""
    if settings.rerank_enabled:
        try:
            ranked = await rerank(query, [doc.content for doc, _ in rows], top_k=top_k)
            results = [(rows[i][0], score) for i, score in ranked]
            header = f"RAG 向量檢索「{query}」的相關文件（已用 cross-encoder 重新排序）："
        except Exception as exc:  # noqa: BLE001
            # Rerank is a precision improvement on top of vector search, not a
            # hard dependency - fall back to plain vector-similarity order
            # rather than failing the whole tool call.
            rerank_note = f"\n（注意：Rerank 失敗，改用向量相似度排序：{exc}）"
            results = [(doc, max(0.0, 1 - float(distance))) for doc, distance in rows[:top_k]]
            header = f"RAG 向量檢索「{query}」的相關文件（依相似度排序）："
    else:
        results = [(doc, max(0.0, 1 - float(distance))) for doc, distance in rows[:top_k]]
        header = f"RAG 向量檢索「{query}」的相關文件（依相似度排序）："

    lines = [header]
    for i, (doc, score) in enumerate(results, start=1):
        lines.append(f"{i}. [{doc.title}] (相關度 {score:.2f})\n{doc.content.strip()}")
    return "\n\n".join(lines) + rerank_note
