# filepath: backend/app/models/chunk.py
"""DocumentChunk ORM model."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document
    from app.models.section import DocumentSection


class DocumentChunk(UUIDMixin, CreatedAtMixin, Base):
    """A text chunk derived from a document section, stored for vector search."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vector_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )

    # ── Relationships ────────────────────────────────────────────
    document: Mapped[Document] = relationship("Document", back_populates="chunks")
    section: Mapped[Optional[DocumentSection]] = relationship(
        "DocumentSection", back_populates="chunks",
    )
    company: Mapped[Company] = relationship("Company", back_populates="document_chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} idx={self.chunk_index} id={self.id}>"
