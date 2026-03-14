# filepath: backend/app/models/document.py
"""Document ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.company import Company
    from app.models.financial import FinancialStatement
    from app.models.section import DocumentSection


class DocType(str, enum.Enum):
    """SEC filing document types."""

    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    TWENTY_F = "20-F"
    DEF14A = "DEF14A"
    OTHER = "OTHER"


class DocStatus(str, enum.Enum):
    """Document processing pipeline status."""

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EMBEDDING = "embedding"
    READY = "ready"
    ERROR = "error"


class Document(UUIDMixin, TimestampMixin, Base):
    """An SEC filing document belonging to a company."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "doc_type", "fiscal_year", "fiscal_quarter",
            name="uq_documents_period",
        ),
        CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4",
            name="chk_quarter_range",
        ),
        CheckConstraint(
            "fiscal_year BETWEEN 1990 AND 2100",
            name="chk_fiscal_year",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, name="doc_type_enum", create_constraint=False, native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    sec_accession: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    storage_bucket: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="filings",
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status_enum", create_constraint=False, native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        server_default="uploaded",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────
    company: Mapped[Company] = relationship("Company", back_populates="documents")
    sections: Mapped[list[DocumentSection]] = relationship(
        "DocumentSection", back_populates="document", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    financial_statements: Mapped[list[FinancialStatement]] = relationship(
        "FinancialStatement", back_populates="document",
    )

    def __repr__(self) -> str:
        return f"<Document {self.doc_type.value} {self.fiscal_year}Q{self.fiscal_quarter or '-'} id={self.id}>"
