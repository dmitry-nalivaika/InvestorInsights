# filepath: backend/tests/integration/test_comparison_api.py
"""Integration tests for the multi-company comparison endpoint (Phase 7).

Tests the full HTTP path for ``POST /api/v1/analysis/compare``.

The AnalysisService is injected via dependency override so no real
database or LLM connection is required.

Test matrix:
  - POST /analysis/compare: success (200), ranked ordering, no_data
    companies sorted last, profile not found (404), too few companies
    (422), too many companies (422)

Tasks: T600, T601, T602
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("API_KEY", "test-api-key-for-analysis-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest
from fastapi.testclient import TestClient

from app.api.middleware.error_handler import NotFoundError
from app.services.analysis_service import AnalysisService

# =====================================================================
# Helpers
# =====================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_PROFILE_ID = uuid.UUID("aaaa1111-1111-1111-1111-111111111111")

_COMPANY_A_ID = uuid.UUID("cccc3333-3333-3333-3333-333333333333")
_COMPANY_B_ID = uuid.UUID("dddd4444-4444-4444-4444-444444444444")
_COMPANY_C_ID = uuid.UUID("eeee5555-5555-5555-5555-555555555555")

_RESULT_A_ID = uuid.UUID("bbbb2222-2222-2222-2222-222222222222")
_RESULT_B_ID = uuid.UUID("bbbb2222-3333-3333-3333-333333333333")
_RESULT_C_ID = uuid.UUID("bbbb2222-4444-4444-4444-444444444444")


def _make_company(company_id: uuid.UUID, ticker: str, name: str) -> MagicMock:
    c = MagicMock(spec=[])
    c.id = company_id
    c.ticker = ticker
    c.name = name
    return c


def _make_result(
    *,
    result_id: uuid.UUID,
    company_id: uuid.UUID,
    ticker: str,
    name: str,
    pct_score: Decimal,
    max_score: Decimal,
    overall_score: Decimal,
    passed: int,
    failed: int,
    criteria_count: int,
    details: list[dict[str, Any]] | None = None,
    summary: str | None = "AI summary.",
) -> MagicMock:
    """Build a mock AnalysisResult ORM object."""
    obj = MagicMock(spec=[])
    obj.id = result_id
    obj.company_id = company_id
    obj.profile_id = _PROFILE_ID
    obj.profile_version = 1
    obj.run_at = _NOW
    obj.overall_score = overall_score
    obj.max_score = max_score
    obj.pct_score = pct_score
    obj.criteria_count = criteria_count
    obj.passed_count = passed
    obj.failed_count = failed
    obj.result_details = details or [
        {
            "criteria_name": "Gross Margin > 40%",
            "category": "profitability",
            "formula": "gross_margin",
            "values_by_year": {"2021": 0.42, "2022": 0.44, "2023": 0.45},
            "latest_value": 0.45,
            "threshold": ">= 0.4",
            "passed": True,
            "has_data": True,
            "weighted_score": 2.0,
            "weight": 2.0,
            "trend": "improving",
            "note": "Trend: improving",
        },
    ]
    obj.summary = summary
    obj.created_at = _NOW

    company = _make_company(company_id, ticker, name)
    obj.company = company

    profile = MagicMock(spec=[])
    profile.name = "Quality Value Investor"
    obj.profile = profile

    return obj


def _make_no_data_result(
    result_id: uuid.UUID, company_id: uuid.UUID, ticker: str, name: str,
) -> MagicMock:
    """Build a result for a company with no financial data."""
    return _make_result(
        result_id=result_id,
        company_id=company_id,
        ticker=ticker,
        name=name,
        pct_score=Decimal("0"),
        max_score=Decimal("0"),
        overall_score=Decimal("0"),
        passed=0,
        failed=0,
        criteria_count=1,
        details=[
            {
                "criteria_name": "Gross Margin > 40%",
                "category": "profitability",
                "formula": "gross_margin",
                "values_by_year": {},
                "latest_value": None,
                "threshold": ">= 0.4",
                "passed": False,
                "has_data": False,
                "weighted_score": 0.0,
                "weight": 2.0,
                "trend": None,
                "note": "No data available",
            },
        ],
        summary=None,
    )


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def mock_service():
    """Pre-configured mock AnalysisService with compare_companies wired."""
    svc = AsyncMock(spec=AnalysisService)

    # Default: two scored companies, A better than B
    result_a = _make_result(
        result_id=_RESULT_A_ID,
        company_id=_COMPANY_A_ID,
        ticker="AAPL",
        name="Apple Inc.",
        pct_score=Decimal("85.00"),
        max_score=Decimal("2.0"),
        overall_score=Decimal("1.7"),
        passed=1,
        failed=0,
        criteria_count=1,
    )
    result_b = _make_result(
        result_id=_RESULT_B_ID,
        company_id=_COMPANY_B_ID,
        ticker="MSFT",
        name="Microsoft Corp.",
        pct_score=Decimal("60.00"),
        max_score=Decimal("2.0"),
        overall_score=Decimal("1.2"),
        passed=1,
        failed=0,
        criteria_count=1,
    )

    svc.compare_companies.return_value = {
        "profile_id": _PROFILE_ID,
        "profile_name": "Quality Value Investor",
        "companies_count": 2,
        "criteria_names": ["Gross Margin > 40%"],
        "ranked_results": [result_a, result_b],  # pre-sorted: A > B
        "no_data_ids": set(),
    }

    return svc


@pytest.fixture()
def client(app, mock_service):
    """TestClient with AnalysisService dependency overridden by mock_service."""
    from app.api.analysis import _get_analysis_service

    app.dependency_overrides[_get_analysis_service] = lambda: mock_service
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(_get_analysis_service, None)


# =====================================================================
# Comparison tests (T600-T602)
# =====================================================================


class TestCompareCompanies:
    """POST /api/v1/analysis/compare."""

    def test_compare_success(self, client, auth_header, mock_service):
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
            "generate_summary": True,
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 200

        data = resp.json()
        assert data["profile_id"] == str(_PROFILE_ID)
        assert data["profile_name"] == "Quality Value Investor"
        assert data["companies_count"] == 2
        assert data["criteria_names"] == ["Gross Margin > 40%"]
        assert len(data["rankings"]) == 2

    def test_compare_ranking_order(self, client, auth_header, mock_service):
        """Companies should be ranked by pct_score descending."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 200

        rankings = resp.json()["rankings"]
        assert rankings[0]["rank"] == 1
        assert rankings[0]["company_ticker"] == "AAPL"
        assert float(rankings[0]["pct_score"]) == 85.00
        assert rankings[1]["rank"] == 2
        assert rankings[1]["company_ticker"] == "MSFT"
        assert float(rankings[1]["pct_score"]) == 60.00

    def test_compare_ranking_fields(self, client, auth_header, mock_service):
        """Each ranking item should contain expected fields."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        item = resp.json()["rankings"][0]

        assert "rank" in item
        assert "company_id" in item
        assert "company_ticker" in item
        assert "company_name" in item
        assert "result_id" in item
        assert "overall_score" in item
        assert "max_score" in item
        assert "pct_score" in item
        assert "grade" in item
        assert "passed_count" in item
        assert "failed_count" in item
        assert "criteria_count" in item
        assert "status" in item
        assert "criteria_results" in item
        assert "summary" in item

    def test_compare_criteria_cells(self, client, auth_header, mock_service):
        """Each ranking should have per-criterion cells."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        cells = resp.json()["rankings"][0]["criteria_results"]

        assert len(cells) == 1
        cell = cells[0]
        assert cell["criteria_name"] == "Gross Margin > 40%"
        assert cell["category"] == "profitability"
        assert cell["formula"] == "gross_margin"
        assert cell["passed"] is True
        assert cell["has_data"] is True
        assert cell["threshold"] == ">= 0.4"
        assert "values_by_year" in cell

    def test_compare_grade_assignment(self, client, auth_header, mock_service):
        """Grades should match A:90-100, B:75-89, C:60-74, D:40-59, F:0-39."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        rankings = resp.json()["rankings"]

        # AAPL 85% → B, MSFT 60% → C
        assert rankings[0]["grade"] == "B"
        assert rankings[1]["grade"] == "C"

    def test_compare_no_data_company_last(self, client, auth_header, mock_service):
        """Companies with no data should be ranked last with status 'no_data'."""
        result_a = _make_result(
            result_id=_RESULT_A_ID,
            company_id=_COMPANY_A_ID,
            ticker="AAPL",
            name="Apple Inc.",
            pct_score=Decimal("85.00"),
            max_score=Decimal("2.0"),
            overall_score=Decimal("1.7"),
            passed=1,
            failed=0,
            criteria_count=1,
        )
        no_data = _make_no_data_result(
            _RESULT_C_ID, _COMPANY_C_ID, "NEWCO", "NewCo Inc.",
        )
        mock_service.compare_companies.return_value = {
            "profile_id": _PROFILE_ID,
            "profile_name": "Quality Value Investor",
            "companies_count": 2,
            "criteria_names": ["Gross Margin > 40%"],
            "ranked_results": [result_a, no_data],
            "no_data_ids": {_COMPANY_C_ID},
        }

        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_C_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 200

        rankings = resp.json()["rankings"]
        assert rankings[0]["company_ticker"] == "AAPL"
        assert rankings[0]["status"] == "scored"
        assert rankings[1]["company_ticker"] == "NEWCO"
        assert rankings[1]["status"] == "no_data"

    def test_compare_three_companies(self, client, auth_header, mock_service):
        """Support 3+ companies in a comparison."""
        result_a = _make_result(
            result_id=_RESULT_A_ID,
            company_id=_COMPANY_A_ID,
            ticker="AAPL",
            name="Apple Inc.",
            pct_score=Decimal("90.00"),
            max_score=Decimal("2.0"),
            overall_score=Decimal("1.8"),
            passed=1,
            failed=0,
            criteria_count=1,
        )
        result_b = _make_result(
            result_id=_RESULT_B_ID,
            company_id=_COMPANY_B_ID,
            ticker="MSFT",
            name="Microsoft Corp.",
            pct_score=Decimal("75.00"),
            max_score=Decimal("2.0"),
            overall_score=Decimal("1.5"),
            passed=1,
            failed=0,
            criteria_count=1,
        )
        result_c = _make_result(
            result_id=_RESULT_C_ID,
            company_id=_COMPANY_C_ID,
            ticker="GOOGL",
            name="Alphabet Inc.",
            pct_score=Decimal("60.00"),
            max_score=Decimal("2.0"),
            overall_score=Decimal("1.2"),
            passed=1,
            failed=0,
            criteria_count=1,
        )
        mock_service.compare_companies.return_value = {
            "profile_id": _PROFILE_ID,
            "profile_name": "Quality Value Investor",
            "companies_count": 3,
            "criteria_names": ["Gross Margin > 40%"],
            "ranked_results": [result_a, result_b, result_c],
            "no_data_ids": set(),
        }

        body = {
            "company_ids": [
                str(_COMPANY_A_ID), str(_COMPANY_B_ID), str(_COMPANY_C_ID),
            ],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 200

        data = resp.json()
        assert data["companies_count"] == 3
        tickers = [r["company_ticker"] for r in data["rankings"]]
        assert tickers == ["AAPL", "MSFT", "GOOGL"]
        # Ranks assigned sequentially
        ranks = [r["rank"] for r in data["rankings"]]
        assert ranks == [1, 2, 3]

    def test_compare_profile_not_found(self, client, auth_header, mock_service):
        mock_service.compare_companies.side_effect = NotFoundError("Profile not found")
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(uuid.uuid4()),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 404

    def test_compare_too_few_companies(self, client, auth_header, mock_service):
        """Minimum 2 companies required."""
        body = {
            "company_ids": [str(_COMPANY_A_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 422

    def test_compare_too_many_companies(self, client, auth_header, mock_service):
        """Maximum 10 companies allowed."""
        body = {
            "company_ids": [str(uuid.uuid4()) for _ in range(11)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        assert resp.status_code == 422

    def test_compare_no_auth(self, app, mock_service):
        """Request without API key should be rejected."""
        from app.api.analysis import _get_analysis_service

        app.dependency_overrides[_get_analysis_service] = lambda: mock_service
        with TestClient(app, raise_server_exceptions=False) as c:
            body = {
                "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
                "profile_id": str(_PROFILE_ID),
            }
            resp = c.post("/api/v1/analysis/compare", json=body)
        app.dependency_overrides.pop(_get_analysis_service, None)
        assert resp.status_code == 401

    def test_compare_scored_status(self, client, auth_header, mock_service):
        """All companies with data should have status 'scored'."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        for r in resp.json()["rankings"]:
            assert r["status"] == "scored"

    def test_compare_summary_present(self, client, auth_header, mock_service):
        """AI summaries should be returned when available."""
        body = {
            "company_ids": [str(_COMPANY_A_ID), str(_COMPANY_B_ID)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/compare", json=body, headers=auth_header)
        for r in resp.json()["rankings"]:
            assert r["summary"] == "AI summary."
