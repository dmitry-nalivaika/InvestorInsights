# filepath: backend/app/models/section.py
"""DocumentSection ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.document import Document


class DocumentSection(UUIDMixin, CreatedAtMixin, Base):
    """A logical section extracted from a parsed document (e.g. Item 1A, Item 7)."""

    __tablename__ = "document_sections"
    __table_args__ = (
        UniqueConstraint("document_id", "section_key", name="uq_section_per_doc"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Relationships ────────────────────────────────────────────
    document: Mapped[Document] = relationship("Document", back_populates="sections")
    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="section",
    )

    def __repr__(self) -> str:
        return f"<DocumentSection {self.section_key!r} id={self.id}>"
