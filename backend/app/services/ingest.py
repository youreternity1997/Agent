"""Turns an uploaded file into pgvector rows: LlamaIndex handles reading the
file and splitting it into chunks; embedding reuses the project's existing
Ollama embedding call (app.core.llm.embed) so there's a single embedding
code path shared with the seed data / rag_search tool.
"""

from pathlib import Path

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.llm import embed
from app.db.database import AsyncSessionLocal
from app.db.models import KBDocument, UploadedFile

settings = get_settings()

TEXT_EXTENSIONS = {".txt", ".md"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS


class IngestError(RuntimeError):
    pass


def _load_documents(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return [Document(text=text)]
    if suffix in PDF_EXTENSIONS:
        from llama_index.readers.file import PDFReader

        return PDFReader().load_data(file=path)
    if suffix in DOCX_EXTENSIONS:
        from llama_index.readers.file import DocxReader

        return DocxReader().load_data(file=path)
    raise IngestError(f"不支援的檔案格式：{suffix}")


def _chunk_documents(documents: list[Document]) -> list[str]:
    splitter = SentenceSplitter(
        chunk_size=settings.upload_chunk_size,
        chunk_overlap=settings.upload_chunk_overlap,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    return [text for node in nodes if (text := node.get_content().strip())]


async def _ingest(session: AsyncSession, uploaded: UploadedFile, path: Path) -> None:
    documents = _load_documents(path)
    chunks = _chunk_documents(documents)
    if not chunks:
        raise IngestError("檔案內容為空或無法擷取文字")

    for i, chunk_text in enumerate(chunks):
        vector = await embed(chunk_text)
        session.add(
            KBDocument(
                uploaded_file_id=uploaded.id,
                title=uploaded.filename,
                content=chunk_text,
                embedding=vector,
                doc_metadata={"source": "upload", "chunk_index": i},
            )
        )
    uploaded.status = "done"
    uploaded.chunk_count = len(chunks)


async def run_ingest_job(file_id: int, path: Path, filename: str) -> None:
    """Entry point for the FastAPI BackgroundTasks worker - owns its own DB
    session since the request-scoped session is already closed by the time
    this runs.
    """
    async with AsyncSessionLocal() as session:
        uploaded = await session.get(UploadedFile, file_id)
        if uploaded is None:
            path.unlink(missing_ok=True)
            return
        try:
            await _ingest(session, uploaded, path)
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - ingestion errors must not crash the worker
            await session.rollback()
            uploaded = await session.get(UploadedFile, file_id)
            if uploaded is not None:
                uploaded.status = "error"
                uploaded.error_message = str(exc)[:2000]
                await session.commit()
        finally:
            path.unlink(missing_ok=True)
