import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_session
from app.db.models import UploadedFile
from app.services.ingest import SUPPORTED_EXTENSIONS, run_ingest_job

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()


def _file_dict(f: UploadedFile) -> dict:
    return {
        "id": f.id,
        "filename": f.filename,
        "content_type": f.content_type,
        "size_bytes": f.size_bytes,
        "chunk_count": f.chunk_count,
        "status": f.status,
        "error_message": f.error_message,
        "created_at": f.created_at.isoformat(),
    }


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)):
    stmt = select(UploadedFile).order_by(UploadedFile.created_at.desc())
    files = (await session.execute(stmt)).scalars().all()
    return [_file_dict(f) for f in files]


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的檔案格式：{suffix or '(無副檔名)'}，"
            f"僅支援 {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > settings.upload_max_file_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"檔案過大（{size_mb:.1f} MB），上限為 {settings.upload_max_file_size_mb} MB",
        )

    record = UploadedFile(
        filename=file.filename or "untitled",
        content_type=file.content_type,
        size_bytes=len(raw),
        status="processing",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    tmp_path = Path(tempfile.gettempdir()) / f"gigabyte-upload-{uuid.uuid4().hex}{suffix}"
    tmp_path.write_bytes(raw)

    background_tasks.add_task(run_ingest_job, record.id, tmp_path, record.filename)

    return _file_dict(record)


@router.delete("/{file_id}")
async def delete_document(file_id: int, session: AsyncSession = Depends(get_session)):
    record = await session.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="檔案不存在")
    await session.delete(record)
    await session.commit()
    return {"status": "deleted", "id": file_id}
