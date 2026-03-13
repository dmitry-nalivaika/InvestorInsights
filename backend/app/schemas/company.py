# filepath: backend/app/schemas/company.py
"""Pydantic schemas for Company endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from app.schemas.common import AppBaseModel, PaginatedResponse


# ── Request schemas ──────────────────────────────────────────────


class CompanyCreate(AppBaseModel):
    """POST /api/v1/companies — create a new company."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker")
    name: Optional[str] = Field(None, max_length=255, description="Auto-resolved from SEC if omitted")
    cik: Optional[str] = Field(None, max_length=20)
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class CompanyUpdate(AppBaseModel):
    """PUT /api/v1/companies/{company_id} — partial update."""

    name: Optional[str] = Field(None, max_length=255)
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


# ── Response schemas ─────────────────────────────────────────────


class CompanyRead(AppBaseModel):
    """Company object returned by list / create / update endpoints."""

    id: uuid.UUID
    ticker: str
    name: str
    cik: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class CompanyListItem(CompanyRead):
    """Extended company item for list responses (includes doc summary stats)."""

    doc_count: int = 0
    latest_filing_date: Optional[date] = None
    readiness_pct: float = 0.0


class CompanyList(PaginatedResponse[CompanyListItem]):
    """Paginated list of companies."""

    pass


class YearRange(AppBaseModel):
    min: Optional[int] = None
    max: Optional[int] = None


class DocumentsSummary(AppBaseModel):
    total: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    year_range: YearRange = Field(default_factory=YearRange)


class FinancialsSummary(AppBaseModel):
    periods_available: int = 0
    year_range: YearRange = Field(default_factory=YearRange)


class CompanyDetail(CompanyRead):
    """GET /api/v1/companies/{company_id} — detailed company with summaries."""

    documents_summary: DocumentsSummary = Field(default_factory=DocumentsSummary)
    financials_summary: FinancialsSummary = Field(default_factory=FinancialsSummary)
    recent_sessions: List[Any] = Field(default_factory=list)  # ChatSessionRead injected later
