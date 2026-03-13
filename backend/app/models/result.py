# filepath: backend/app/models/result.py
"""AnalysisResult ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.profile import AnalysisProfile


class AnalysisResult(UUIDMixin, CreatedAtMixin, Base):
    """The outcome of running an analysis profile against a company."""

    __tablename__ = "analysis_results"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"),
    )
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=text("0"),
    )
    max_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=text("0"),
    )
    pct_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0"),
    )
    criteria_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    passed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )
    result_details: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"),
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────
    company: Mapped[Company] = relationship(
        "Company", back_populates="analysis_results",
    )
    profile: Mapped[AnalysisProfile] = relationship(
        "AnalysisProfile", back_populates="results",
    )

    def __repr__(self) -> str:
        return f"<AnalysisResult {self.pct_score}% company={self.company_id} id={self.id}>"
