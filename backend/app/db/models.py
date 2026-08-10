from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768  # nomic-embed-text output dimension


class Base(DeclarativeBase):
    pass


class Motherboard(Base):
    __tablename__ = "motherboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    series: Mapped[str] = mapped_column(String(60))
    socket: Mapped[str] = mapped_column(String(30))
    chipset: Mapped[str] = mapped_column(String(30))
    form_factor: Mapped[str] = mapped_column(String(20))
    memory_type: Mapped[str] = mapped_column(String(20))
    memory_slots: Mapped[int] = mapped_column(Integer)
    max_memory_gb: Mapped[int] = mapped_column(Integer)
    pcie_version: Mapped[str] = mapped_column(String(20))
    m2_slots: Mapped[int] = mapped_column(Integer)
    wifi: Mapped[bool] = mapped_column(default=False)
    price_twd: Mapped[int] = mapped_column(Integer)
    release_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    extra_specs: Mapped[dict] = mapped_column(JSON, default=dict)

    documents: Mapped[list["KBDocument"]] = relationship(back_populates="motherboard")


class UploadedFile(Base):
    """Metadata for a file uploaded via the knowledge-base ingestion pipeline."""

    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(260))
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list["KBDocument"]] = relationship(back_populates="uploaded_file")


class KBDocument(Base):
    """Chunks of product-knowledge text used for RAG (semantic search)."""

    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    motherboard_id: Mapped[int | None] = mapped_column(ForeignKey("motherboards.id"), nullable=True)
    uploaded_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    motherboard: Mapped["Motherboard | None"] = relationship(back_populates="documents")
    uploaded_file: Mapped["UploadedFile | None"] = relationship(back_populates="documents")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="新對話")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
