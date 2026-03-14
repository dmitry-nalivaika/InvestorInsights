# filepath: backend/app/models/company.py
"""Company ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.document import Document
    from app.models.financial import FinancialStatement
    from app.models.result import AnalysisResult
    from app.models.session import ChatSession


class Company(UUIDMixin, TimestampMixin, Base):
    """A publicly traded company tracked by the platform."""

    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cik: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"),
    )

    # ── Relationships ────────────────────────────────────────────
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="company", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    financial_statements: Mapped[list[FinancialStatement]] = relationship(
        "FinancialStatement", back_populates="company", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="company", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analysis_results: Mapped[list[AnalysisResult]] = relationship(
        "AnalysisResult", back_populates="company", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document_chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="company", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker!r} id={self.id}>"
