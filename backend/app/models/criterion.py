# filepath: backend/app/models/criterion.py
"""AnalysisCriterion ORM model."""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.profile import AnalysisProfile


class CriteriaCategory(str, enum.Enum):
    """Categories for grouping analysis criteria."""

    PROFITABILITY = "profitability"
    VALUATION = "valuation"
    GROWTH = "growth"
    LIQUIDITY = "liquidity"
    SOLVENCY = "solvency"
    EFFICIENCY = "efficiency"
    DIVIDEND = "dividend"
    QUALITY = "quality"
    CUSTOM = "custom"


class ComparisonOp(str, enum.Enum):
    """Comparison operators for threshold evaluation."""

    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "="
    BETWEEN = "between"
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"


class AnalysisCriterion(UUIDMixin, CreatedAtMixin, Base):
    """A single metric/threshold rule within an analysis profile."""

    __tablename__ = "analysis_criteria"
    __table_args__ = (
        CheckConstraint("weight > 0", name="chk_weight_positive"),
        CheckConstraint(
            "lookback_years > 0 AND lookback_years <= 20",
            name="chk_lookback_positive",
        ),
        CheckConstraint(
            "comparison != 'between' OR (threshold_low IS NOT NULL AND threshold_high IS NOT NULL)",
            name="chk_threshold_between",
        ),
        CheckConstraint(
            "comparison IN ('between', 'trend_up', 'trend_down') OR threshold_value IS NOT NULL",
            name="chk_threshold_single",
        ),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[CriteriaCategory] = mapped_column(
        Enum(
            CriteriaCategory,
            name="criteria_category_enum",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    formula: Mapped[str] = mapped_column(String(500), nullable=False)
    is_custom_formula: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    comparison: Mapped[ComparisonOp] = mapped_column(
        Enum(
            ComparisonOp,
            name="comparison_op_enum",
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 6), nullable=True,
    )
    threshold_low: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 6), nullable=True,
    )
    threshold_high: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 6), nullable=True,
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=text("1.0"),
    )
    lookback_years: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )

    # ── Relationships ────────────────────────────────────────────
    profile: Mapped[AnalysisProfile] = relationship(
        "AnalysisProfile", back_populates="criteria",
    )

    def __repr__(self) -> str:
        return f"<AnalysisCriterion {self.name!r} [{self.category.value}] id={self.id}>"
