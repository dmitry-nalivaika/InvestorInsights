# filepath: backend/tests/integration/test_analysis_api.py
"""Integration tests for Analysis API routes (Phase 6).

Tests the full HTTP path: request → FastAPI routing → validation →
response serialization → status codes.

The AnalysisService is injected via dependency override.

Test matrix:
  - POST /analysis/profiles: success (201), duplicate (409)
  - GET  /analysis/profiles: list
  - GET  /analysis/profiles/{id}: found (200), not found (404)
  - PUT  /analysis/profiles/{id}: success (200)
  - DELETE /analysis/profiles/{id}: success (204), not found (404)
  - POST /analysis/run: success, not found (404)
  - GET  /analysis/results: list with filters
  - GET  /analysis/results/{id}: found, not found
  - GET  /analysis/results/{id}/export: download
  - GET  /analysis/formulas: lists 25+ formulas
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

from app.api.middleware.error_handler import ConflictError, NotFoundError
from app.services.analysis_service import AnalysisService

# =====================================================================
# Helpers
# =====================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_PROFILE_ID = uuid.UUID("aaaa1111-1111-1111-1111-111111111111")
_RESULT_ID = uuid.UUID("bbbb2222-2222-2222-2222-222222222222")
_COMPANY_ID = uuid.UUID("cccc3333-3333-3333-3333-333333333333")


def _make_profile(**overrides: Any) -> MagicMock:
    """Mock AnalysisProfile ORM object."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _PROFILE_ID)
    obj.name = overrides.get("name", "Quality Value Investor")
    obj.description = overrides.get("description", "A balanced profile")
    obj.is_default = overrides.get("is_default", True)
    obj.version = overrides.get("version", 1)
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    obj.criteria = overrides.get("criteria", [])
    return obj


def _make_criterion(**overrides: Any) -> MagicMock:
    """Mock AnalysisCriterion ORM object."""
    from app.models.criterion import ComparisonOp, CriteriaCategory

    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", uuid.uuid4())
    obj.profile_id = overrides.get("profile_id", _PROFILE_ID)
    obj.name = overrides.get("name", "Gross Margin > 40%")
    obj.category = overrides.get("category", CriteriaCategory.PROFITABILITY)
    obj.description = overrides.get("description")
    obj.formula = overrides.get("formula", "gross_margin")
    obj.is_custom_formula = overrides.get("is_custom_formula", False)
    obj.comparison = overrides.get("comparison", ComparisonOp.GTE)
    obj.threshold_value = overrides.get("threshold_value", Decimal("0.40"))
    obj.threshold_low = overrides.get("threshold_low")
    obj.threshold_high = overrides.get("threshold_high")
    obj.weight = overrides.get("weight", Decimal("2.0"))
    obj.lookback_years = overrides.get("lookback_years", 5)
    obj.enabled = overrides.get("enabled", True)
    obj.sort_order = overrides.get("sort_order", 0)
    obj.created_at = overrides.get("created_at", _NOW)
    return obj


def _make_result(**overrides: Any) -> MagicMock:
    """Mock AnalysisResult ORM object."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _RESULT_ID)
    obj.company_id = overrides.get("company_id", _COMPANY_ID)
    obj.profile_id = overrides.get("profile_id", _PROFILE_ID)
    obj.profile_version = overrides.get("profile_version", 1)
    obj.run_at = overrides.get("run_at", _NOW)
    obj.overall_score = overrides.get("overall_score", Decimal("18.5"))
    obj.max_score = overrides.get("max_score", Decimal("24.5"))
    obj.pct_score = overrides.get("pct_score", Decimal("75.51"))
    obj.criteria_count = overrides.get("criteria_count", 15)
    obj.passed_count = overrides.get("passed_count", 10)
    obj.failed_count = overrides.get("failed_count", 5)
    obj.result_details = overrides.get("result_details", [
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
    ])
    obj.summary = overrides.get("summary", "Strong performance overall.")
    obj.created_at = overrides.get("created_at", _NOW)

    # Company relationship
    company = MagicMock(spec=[])
    company.ticker = "AAPL"
    company.name = "Apple Inc."
    obj.company = overrides.get("company", company)

    # Profile relationship
    profile = MagicMock(spec=[])
    profile.name = "Quality Value Investor"
    obj.profile = overrides.get("profile", profile)

    return obj


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def mock_service():
    """Pre-configured mock AnalysisService."""
    svc = AsyncMock(spec=AnalysisService)

    # Profile CRUD defaults
    svc.create_profile.return_value = _make_profile(criteria=[_make_criterion()])
    svc.get_profile.return_value = _make_profile(criteria=[_make_criterion()])
    svc.list_profiles.return_value = ([_make_profile()], 1)
    svc.update_profile.return_value = _make_profile(version=2, criteria=[_make_criterion()])
    svc.delete_profile.return_value = None

    # Analysis run
    svc.run_analysis.return_value = [_make_result()]

    # Results
    svc.get_result.return_value = _make_result()
    svc.list_results.return_value = ([_make_result()], 1)

    return svc


@pytest.fixture()
def client(app, mock_service):
    """TestClient with AnalysisService dependency overridden by mock_service.

    This shadows the conftest ``client`` fixture so every test in this
    module hits the mock instead of a real DB-backed service.
    """
    from app.api.analysis import _get_analysis_service

    app.dependency_overrides[_get_analysis_service] = lambda: mock_service
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(_get_analysis_service, None)


# =====================================================================
# Profile CRUD tests (T504)
# =====================================================================


class TestCreateProfile:
    def test_create_success(self, client, auth_header, mock_service):
        body = {
            "name": "Test Profile",
            "description": "Test",
            "criteria": [
                {
                    "name": "GM > 40%",
                    "category": "profitability",
                    "formula": "gross_margin",
                    "comparison": ">=",
                    "threshold_value": "0.40",
                    "weight": "2.0",
                },
            ],
        }
        resp = client.post("/api/v1/analysis/profiles", json=body, headers=auth_header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Quality Value Investor"
        assert "criteria" in data

    def test_create_duplicate_name(self, client, auth_header, mock_service):
        mock_service.create_profile.side_effect = ConflictError("exists")
        body = {
            "name": "Duplicate",
            "criteria": [
                {
                    "name": "Test",
                    "category": "profitability",
                    "formula": "gross_margin",
                    "comparison": ">=",
                    "threshold_value": "0.40",
                },
            ],
        }
        resp = client.post("/api/v1/analysis/profiles", json=body, headers=auth_header)
        assert resp.status_code == 409


class TestListProfiles:
    def test_list_success(self, client, auth_header, mock_service):
        resp = client.get("/api/v1/analysis/profiles", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Quality Value Investor"


class TestGetProfile:
    def test_get_found(self, client, auth_header, mock_service):
        resp = client.get(f"/api/v1/analysis/profiles/{_PROFILE_ID}", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Quality Value Investor"
        assert "criteria" in data

    def test_get_not_found(self, client, auth_header, mock_service):
        mock_service.get_profile.side_effect = NotFoundError("not found")
        resp = client.get(f"/api/v1/analysis/profiles/{uuid.uuid4()}", headers=auth_header)
        assert resp.status_code == 404


class TestUpdateProfile:
    def test_update_success(self, client, auth_header, mock_service):
        body = {"name": "Updated Name"}
        resp = client.put(
            f"/api/v1/analysis/profiles/{_PROFILE_ID}", json=body, headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2

    def test_update_not_found(self, client, auth_header, mock_service):
        mock_service.update_profile.side_effect = NotFoundError("not found")
        resp = client.put(
            f"/api/v1/analysis/profiles/{uuid.uuid4()}",
            json={"name": "X"},
            headers=auth_header,
        )
        assert resp.status_code == 404


class TestDeleteProfile:
    def test_delete_success(self, client, auth_header, mock_service):
        resp = client.delete(
            f"/api/v1/analysis/profiles/{_PROFILE_ID}", headers=auth_header,
        )
        assert resp.status_code == 204

    def test_delete_not_found(self, client, auth_header, mock_service):
        mock_service.delete_profile.side_effect = NotFoundError("not found")
        resp = client.delete(
            f"/api/v1/analysis/profiles/{uuid.uuid4()}", headers=auth_header,
        )
        assert resp.status_code == 404


# =====================================================================
# Analysis run tests (T509)
# =====================================================================


class TestRunAnalysis:
    def test_run_success(self, client, auth_header, mock_service):
        body = {
            "company_ids": [str(_COMPANY_ID)],
            "profile_id": str(_PROFILE_ID),
            "generate_summary": True,
        }
        resp = client.post("/api/v1/analysis/run", json=body, headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["company_ticker"] == "AAPL"
        assert result["grade"] in ("A", "B", "C", "D", "F")
        assert len(result["criteria_results"]) == 1
        assert result["criteria_results"][0]["criteria_name"] == "Gross Margin > 40%"

    def test_run_profile_not_found(self, client, auth_header, mock_service):
        mock_service.run_analysis.side_effect = NotFoundError("Profile not found")
        body = {
            "company_ids": [str(_COMPANY_ID)],
            "profile_id": str(uuid.uuid4()),
        }
        resp = client.post("/api/v1/analysis/run", json=body, headers=auth_header)
        assert resp.status_code == 404

    def test_run_too_many_companies(self, client, auth_header, mock_service):
        body = {
            "company_ids": [str(uuid.uuid4()) for _ in range(11)],
            "profile_id": str(_PROFILE_ID),
        }
        resp = client.post("/api/v1/analysis/run", json=body, headers=auth_header)
        assert resp.status_code == 422


# =====================================================================
# Results tests (T512, T517)
# =====================================================================


class TestListResults:
    def test_list_success(self, client, auth_header, mock_service):
        resp = client.get("/api/v1/analysis/results", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_list_with_filters(self, client, auth_header, mock_service):
        resp = client.get(
            "/api/v1/analysis/results",
            params={"company_id": str(_COMPANY_ID)},
            headers=auth_header,
        )
        assert resp.status_code == 200


class TestGetResult:
    def test_get_found(self, client, auth_header, mock_service):
        resp = client.get(
            f"/api/v1/analysis/results/{_RESULT_ID}", headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_ticker"] == "AAPL"
        assert data["summary"] == "Strong performance overall."

    def test_get_not_found(self, client, auth_header, mock_service):
        mock_service.get_result.side_effect = NotFoundError("not found")
        resp = client.get(
            f"/api/v1/analysis/results/{uuid.uuid4()}", headers=auth_header,
        )
        assert resp.status_code == 404


class TestExportResult:
    def test_export_success(self, client, auth_header, mock_service):
        resp = client.get(
            f"/api/v1/analysis/results/{_RESULT_ID}/export", headers=auth_header,
        )
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert "AAPL" in resp.headers.get("content-disposition", "")
        data = resp.json()
        assert data["company_ticker"] == "AAPL"

    def test_export_not_found(self, client, auth_header, mock_service):
        mock_service.get_result.side_effect = NotFoundError("not found")
        resp = client.get(
            f"/api/v1/analysis/results/{uuid.uuid4()}/export", headers=auth_header,
        )
        assert resp.status_code == 404


# =====================================================================
# Formulas endpoint (T513)
# =====================================================================


class TestListFormulas:
    def test_list_formulas(self, client, auth_header):
        resp = client.get("/api/v1/analysis/formulas", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "formulas" in data
        assert len(data["formulas"]) >= 25
        # Check first formula has required fields
        f = data["formulas"][0]
        assert "name" in f
        assert "category" in f
        assert "description" in f
        assert "required_fields" in f

    def test_formula_categories(self, client, auth_header):
        resp = client.get("/api/v1/analysis/formulas", headers=auth_header)
        categories = {f["category"] for f in resp.json()["formulas"]}
        assert "profitability" in categories
        assert "growth" in categories
