# filepath: backend/app/models/financial.py
"""FinancialStatement ORM model."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document


class FinancialStatement(UUIDMixin, TimestampMixin, Base):
    """Structured financial data for a company period, sourced from XBRL or parsed filings."""

    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "fiscal_year", "fiscal_quarter",
            name="uq_financial_period",
        ),
        CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4",
            name="chk_fin_quarter",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD",
    )
    statement_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="xbrl_api",
    )
    raw_xbrl_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────
    company: Mapped[Company] = relationship(
        "Company", back_populates="financial_statements",
    )
    document: Mapped[Optional[Document]] = relationship(
        "Document", back_populates="financial_statements",
    )

    def __repr__(self) -> str:
        q = f"Q{self.fiscal_quarter}" if self.fiscal_quarter else "FY"
        return f"<FinancialStatement {self.fiscal_year}{q} id={self.id}>"
