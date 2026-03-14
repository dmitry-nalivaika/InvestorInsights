# filepath: backend/app/models/profile.py
"""AnalysisProfile ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.criterion import AnalysisCriterion
    from app.models.result import AnalysisResult


class AnalysisProfile(UUIDMixin, TimestampMixin, Base):
    """A named set of analysis criteria used to evaluate companies."""

    __tablename__ = "analysis_profiles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"),
    )

    # ── Relationships ────────────────────────────────────────────
    criteria: Mapped[list[AnalysisCriterion]] = relationship(
        "AnalysisCriterion", back_populates="profile", cascade="all, delete-orphan",
        passive_deletes=True, order_by="AnalysisCriterion.sort_order",
    )
    results: Mapped[list[AnalysisResult]] = relationship(
        "AnalysisResult", back_populates="profile", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<AnalysisProfile {self.name!r} v{self.version} id={self.id}>"
