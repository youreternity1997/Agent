"""RAG vector-store admin endpoints: browse individual kb_documents chunks,
delete one chunk, or wipe the whole RAG database (all chunks + uploaded-file
metadata) in one shot.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import KBDocument, Motherboard, UploadedFile

router = APIRouter(prefix="/api/rag", tags=["rag"])

PREVIEW_LEN = 200


def _chunk_dict(doc: KBDocument, motherboard_name: str | None) -> dict:
    content = doc.content
    preview = content if len(content) <= PREVIEW_LEN else content[:PREVIEW_LEN] + "…"
    return {
        "id": doc.id,
        "title": doc.title,
        "content": content,
        "content_preview": preview,
        "motherboard_id": doc.motherboard_id,
        "motherboard_name": motherboard_name,
        "uploaded_file_id": doc.uploaded_file_id,
        "doc_metadata": doc.doc_metadata,
    }


@router.get("")
async def list_chunks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    uploaded_file_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(KBDocument, Motherboard.model_name).outerjoin(
        Motherboard, KBDocument.motherboard_id == Motherboard.id
    )
    count_stmt = select(func.count()).select_from(KBDocument)
    if uploaded_file_id is not None:
        stmt = stmt.where(KBDocument.uploaded_file_id == uploaded_file_id)
        count_stmt = count_stmt.where(KBDocument.uploaded_file_id == uploaded_file_id)
    stmt = stmt.order_by(KBDocument.id.desc()).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).all()
    total = (await session.execute(count_stmt)).scalar_one()
    return {
        "total": total,
        "chunks": [_chunk_dict(doc, mb_name) for doc, mb_name in rows],
    }


@router.delete("/{chunk_id}")
async def delete_chunk(chunk_id: int, session: AsyncSession = Depends(get_session)):
    doc = await session.get(KBDocument, chunk_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="片段不存在")

    uploaded_file_id = doc.uploaded_file_id
    await session.delete(doc)

    if uploaded_file_id is not None:
        uploaded = await session.get(UploadedFile, uploaded_file_id)
        if uploaded is not None and uploaded.chunk_count > 0:
            uploaded.chunk_count -= 1

    await session.commit()
    return {"status": "deleted", "id": chunk_id}


@router.delete("")
async def clear_rag_database(session: AsyncSession = Depends(get_session)):
    """Wipe the entire RAG vector store: every kb_documents chunk plus every
    uploaded-file record (both upload-sourced and seed-sourced chunks)."""
    await session.execute(delete(KBDocument))
    await session.execute(delete(UploadedFile))
    await session.commit()
    return {"status": "cleared"}
