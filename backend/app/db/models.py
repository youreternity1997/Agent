from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Integer, JSON, String, Text
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


class KBDocument(Base):
    """Chunks of product-knowledge text used for RAG (semantic search)."""

    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    motherboard_id: Mapped[int | None] = mapped_column(ForeignKey("motherboards.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    motherboard: Mapped["Motherboard | None"] = relationship(back_populates="documents")
