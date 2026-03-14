# filepath: backend/app/schemas/financial.py
"""Pydantic schemas for Financial Data endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import Field

from app.schemas.common import AppBaseModel

# ── Response schemas ─────────────────────────────────────────────


class FinancialPeriod(AppBaseModel):
    """A single fiscal period's structured financial data."""

    fiscal_year: int
    fiscal_quarter: int | None = None
    period_end_date: date
    currency: str = "USD"
    source: str = "xbrl_api"
    income_statement: dict[str, Any] = Field(default_factory=dict)
    balance_sheet: dict[str, Any] = Field(default_factory=dict)
    cash_flow: dict[str, Any] = Field(default_factory=dict)


class FinancialsResponse(AppBaseModel):
    """GET /api/v1/companies/{company_id}/financials."""

    company_id: uuid.UUID
    periods: list[FinancialPeriod] = Field(default_factory=list)


class FinancialExportMeta(AppBaseModel):
    """Metadata returned alongside CSV export (for programmatic consumers)."""

    company_id: uuid.UUID
    ticker: str
    period_type: str  # "annual" | "quarterly"
    periods_count: int
    start_year: int | None = None
    end_year: int | None = None
