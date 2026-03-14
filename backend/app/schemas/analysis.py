# filepath: backend/app/schemas/analysis.py
"""Pydantic schemas for Analysis endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.models.criterion import (  # noqa: TC001 - runtime dep for Pydantic
    ComparisonOp,
    CriteriaCategory,
)
from app.schemas.common import AppBaseModel, PaginatedResponse

# ── Criteria schemas ─────────────────────────────────────────────


class CriterionDef(AppBaseModel):
    """A single criterion definition within a profile create/update payload."""

    name: str = Field(..., max_length=100)
    category: CriteriaCategory
    description: str | None = None
    formula: str = Field(..., max_length=500)
    is_custom_formula: bool = False
    comparison: ComparisonOp
    threshold_value: Decimal | None = None
    threshold_low: Decimal | None = None
    threshold_high: Decimal | None = None
    weight: Decimal = Field(Decimal("1.0"), gt=0)
    lookback_years: int = Field(5, ge=1, le=20)
    enabled: bool = True
    sort_order: int = 0


class CriterionRead(CriterionDef):
    """Criterion as returned by the API."""

    id: uuid.UUID
    profile_id: uuid.UUID
    created_at: datetime


# ── Profile schemas ──────────────────────────────────────────────


class ProfileCreate(AppBaseModel):
    """POST /api/v1/analysis/profiles."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    is_default: bool = False
    criteria: list[CriterionDef] = Field(..., min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        # Note: AppBaseModel has str_strip_whitespace=True, which strips
        # before min_length checks.  This validator is a defensive second
        # layer that catches any edge case the Pydantic config doesn't cover.
        v = v.strip()
        if not v:
            raise ValueError("Profile name must not be blank")
        return v


class ProfileUpdate(AppBaseModel):
    """PUT /api/v1/analysis/profiles/{profile_id}."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    is_default: bool | None = None
    criteria: list[CriterionDef] | None = Field(None, min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        # See note on ProfileCreate.strip_name above.
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Profile name must not be blank")
        return v


class ProfileRead(AppBaseModel):
    """Analysis profile returned by the API."""

    id: uuid.UUID
    name: str
    description: str | None = None
    is_default: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ProfileDetail(ProfileRead):
    """Profile with full criteria list."""

    criteria: list[CriterionRead] = Field(default_factory=list)


class ProfileList(PaginatedResponse[ProfileRead]):
    """Paginated list of analysis profiles."""

    pass


# ── Run request / result schemas ─────────────────────────────────


class AnalysisRunRequest(AppBaseModel):
    """POST /api/v1/analysis/run."""

    company_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)
    profile_id: uuid.UUID
    generate_summary: bool = True

    @field_validator("company_ids")
    @classmethod
    def no_duplicate_company_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) != len(set(v)):
            raise ValueError("company_ids must not contain duplicates")
        return v


class CriteriaResultItem(AppBaseModel):
    """Result of a single criterion evaluation within an analysis run."""

    criteria_name: str
    category: str
    formula: str
    values_by_year: dict[int, float | None] = Field(default_factory=dict)
    latest_value: float | None = None
    threshold: str = ""  # human-readable, e.g. ">= 0.15"
    passed: bool = False
    weighted_score: float = 0.0
    trend: str | None = None
    note: str | None = None


class AnalysisResultRead(AppBaseModel):
    """A single company's analysis result."""

    id: uuid.UUID
    company_id: uuid.UUID
    company_ticker: str | None = None
    company_name: str | None = None
    profile_id: uuid.UUID
    profile_version: int
    run_at: datetime
    overall_score: Decimal
    max_score: Decimal
    pct_score: Decimal
    grade: str = ""  # A | B | C | D | F
    criteria_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    criteria_results: list[CriteriaResultItem] = Field(default_factory=list)
    summary: str | None = None
    created_at: datetime


class AnalysisRunResponse(AppBaseModel):
    """Response for POST /api/v1/analysis/run."""

    results: list[AnalysisResultRead]


class AnalysisResultList(PaginatedResponse[AnalysisResultRead]):
    """Paginated list of analysis results."""

    pass


# ── Formula reference ────────────────────────────────────────────


class FormulaInfo(AppBaseModel):
    """Description of a built-in financial formula."""

    name: str
    category: str
    description: str
    required_fields: list[str] = Field(default_factory=list)
    example: str | None = None


class FormulaListResponse(AppBaseModel):
    """Response for GET /api/v1/analysis/formulas."""

    formulas: list[FormulaInfo]


# ── Comparison schemas (T600-T601) ───────────────────────────────


class ComparisonRequest(AppBaseModel):
    """POST /api/v1/analysis/compare."""

    company_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=10)
    profile_id: uuid.UUID
    generate_summary: bool = True

    @field_validator("company_ids")
    @classmethod
    def no_duplicate_company_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) != len(set(v)):
            raise ValueError("company_ids must not contain duplicates")
        return v


class CompanyCriterionCell(AppBaseModel):
    """One cell in the comparison matrix: a single criterion for a single company."""

    criteria_name: str
    category: str
    formula: str
    latest_value: float | None = None
    threshold: str = ""
    passed: bool = False
    has_data: bool = True
    weighted_score: float = 0.0
    weight: float = 0.0
    trend: str | None = None
    values_by_year: dict[int, float | None] = Field(default_factory=dict)


class CompanyComparisonItem(AppBaseModel):
    """One company's row in the comparison table, ranked by overall score."""

    rank: int
    company_id: uuid.UUID
    company_ticker: str | None = None
    company_name: str | None = None
    result_id: uuid.UUID
    overall_score: Decimal
    max_score: Decimal
    pct_score: Decimal
    grade: str
    passed_count: int = 0
    failed_count: int = 0
    criteria_count: int = 0
    status: str = "scored"  # "scored" | "no_data"
    criteria_results: list[CompanyCriterionCell] = Field(default_factory=list)
    summary: str | None = None


class ComparisonResponse(AppBaseModel):
    """Response for POST /api/v1/analysis/compare — ranked comparison table."""

    profile_id: uuid.UUID
    profile_name: str
    companies_count: int
    criteria_names: list[str] = Field(
        default_factory=list,
        description="Ordered list of criterion names (column headers for the matrix)",
    )
    rankings: list[CompanyComparisonItem] = Field(
        default_factory=list,
        description="Companies ranked by overall score descending (no_data companies last)",
    )
