# filepath: backend/app/schemas/company.py
"""Pydantic schemas for Company endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import AppBaseModel, PaginatedResponse

# ── Request schemas ──────────────────────────────────────────────


class CompanyCreate(AppBaseModel):
    """POST /api/v1/companies — create a new company."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker")
    name: str | None = Field(None, max_length=255, description="Auto-resolved from SEC if omitted")
    cik: str | None = Field(None, max_length=20)
    sector: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=100)

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class CompanyUpdate(AppBaseModel):
    """PUT /api/v1/companies/{company_id} — partial update."""

    name: str | None = Field(None, max_length=255)
    sector: str | None = Field(None, max_length=100)
    industry: str | None = Field(None, max_length=100)
    description: str | None = None


# ── Response schemas ─────────────────────────────────────────────


class CompanyRead(AppBaseModel):
    """Company object returned by list / create / update endpoints."""

    id: uuid.UUID
    ticker: str
    name: str
    cik: str | None = None
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class CompanyListItem(CompanyRead):
    """Extended company item for list responses (includes doc summary stats)."""

    doc_count: int = 0
    latest_filing_date: date | None = None
    readiness_pct: float = 0.0


class CompanyList(PaginatedResponse[CompanyListItem]):
    """Paginated list of companies."""

    pass


class YearRange(AppBaseModel):
    min: int | None = None
    max: int | None = None


class DocumentsSummary(AppBaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    year_range: YearRange = Field(default_factory=YearRange)


class FinancialsSummary(AppBaseModel):
    periods_available: int = 0
    year_range: YearRange = Field(default_factory=YearRange)


class CompanyDetail(CompanyRead):
    """GET /api/v1/companies/{company_id} — detailed company with summaries."""

    documents_summary: DocumentsSummary = Field(default_factory=DocumentsSummary)
    financials_summary: FinancialsSummary = Field(default_factory=FinancialsSummary)
    recent_sessions: list[Any] = Field(default_factory=list)  # ChatSessionRead injected later
