# filepath: backend/tests/integration/test_companies_api.py
"""Integration tests for Company CRUD API routes.

Tests the full HTTP path: request → FastAPI routing → validation →
response serialization → status codes.

The CompanyService is injected via dependency override so we can
test the API layer without a real database.  The SEC client is
also mocked.  Real Postgres integration is covered when running
against testcontainers (CI).

Test matrix (from testing-strategy.md §3.1):
  - POST /companies: success (201), duplicate ticker (409)
  - GET  /companies: empty list, with data, search filter
  - GET  /companies/{id}: found (200), not found (404)
  - PUT  /companies/{id}: success (200), not found (404)
  - DELETE /companies/{id}: success (204), missing confirm (422), not found (404)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Env vars must be set BEFORE importing app modules.
os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest
from fastapi.testclient import TestClient

from app.api.middleware.error_handler import ConflictError, NotFoundError
from app.services.company_service import CompanyService

# =====================================================================
# Helpers
# =====================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_COMPANY_ID_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_company_obj(**overrides: Any) -> MagicMock:
    """Build a mock that quacks like a Company ORM instance.

    Pydantic's `model_validate(obj, from_attributes=True)` calls
    `getattr(obj, field_name)`, so we set every field the schema needs.
    Uses `spec=[]` to prevent MagicMock from auto-creating attributes
    that would confuse Pydantic (e.g. documents_summary).
    """
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _COMPANY_ID)
    obj.ticker = overrides.get("ticker", "AAPL")
    obj.name = overrides.get("name", "Apple Inc.")
    obj.cik = overrides.get("cik", "0000320193")
    obj.sector = overrides.get("sector", "Technology")
    obj.industry = overrides.get("industry")
    obj.description = overrides.get("description")
    obj.metadata_ = overrides.get("metadata_")
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    return obj


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def mock_service() -> AsyncMock:
    """Return an AsyncMock of CompanyService."""
    svc = AsyncMock(spec=CompanyService)
    # T105 — pre-configure summary stat defaults so list/detail endpoints work
    svc.get_bulk_summary_stats.return_value = {}
    svc.get_detail_summary.return_value = {
        "documents_summary": {
            "total": 0,
            "by_status": {},
            "by_type": {},
            "year_range": {"min": None, "max": None},
        },
        "financials_summary": {
            "periods_available": 0,
            "year_range": {"min": None, "max": None},
        },
        "recent_sessions": [],
    }
    return svc


@pytest.fixture()
def client(app, mock_service: AsyncMock) -> TestClient:  # type: ignore[override]
    """TestClient with CompanyService dependency overridden."""
    from app.api.companies import _get_company_service

    app.dependency_overrides[_get_company_service] = lambda: mock_service
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# =====================================================================
# POST /api/v1/companies
# =====================================================================


class TestCreateCompany:
    """POST /api/v1/companies."""

    def test_create_success(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.create_company.return_value = _make_company_obj()

        resp = client.post(
            "/api/v1/companies",
            json={"ticker": "aapl"},
            headers=auth_header,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert body["name"] == "Apple Inc."
        assert "id" in body
        mock_service.create_company.assert_awaited_once()

    def test_create_duplicate_ticker(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.create_company.side_effect = ConflictError(
            "Company with ticker 'AAPL' already exists"
        )

        resp = client.post(
            "/api/v1/companies",
            json={"ticker": "AAPL"},
            headers=auth_header,
        )

        assert resp.status_code == 409
        assert "conflict" in resp.json()["error"]

    def test_create_missing_ticker(
        self, client: TestClient, auth_header: dict,
    ) -> None:
        """Pydantic validation — ticker is required."""
        resp = client.post(
            "/api/v1/companies",
            json={},
            headers=auth_header,
        )

        assert resp.status_code == 422

    def test_create_no_auth(self, client: TestClient) -> None:
        """No API key → 401."""
        # Need a fresh client without auth override for this test
        resp = client.post("/api/v1/companies", json={"ticker": "AAPL"})
        assert resp.status_code == 401


# =====================================================================
# GET /api/v1/companies
# =====================================================================


class TestListCompanies:
    """GET /api/v1/companies."""

    def test_list_empty(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.list_companies.return_value = ([], 0)

        resp = client.get("/api/v1/companies", headers=auth_header)

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["limit"] == 50
        assert body["offset"] == 0

    def test_list_with_data(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        companies = [
            _make_company_obj(id=_COMPANY_ID, ticker="AAPL"),
            _make_company_obj(id=_COMPANY_ID_2, ticker="MSFT", name="Microsoft"),
        ]
        mock_service.list_companies.return_value = (companies, 2)
        # T105 — supply summary stats for the list endpoint
        from datetime import date
        mock_service.get_bulk_summary_stats.return_value = {
            _COMPANY_ID: {
                "doc_count": 3,
                "latest_filing_date": date(2024, 3, 15),
                "readiness_pct": 66.7,
            },
            _COMPANY_ID_2: {
                "doc_count": 1,
                "latest_filing_date": date(2023, 12, 31),
                "readiness_pct": 100.0,
            },
        }

        resp = client.get("/api/v1/companies", headers=auth_header)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        tickers = [item["ticker"] for item in body["items"]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

        # T105 — Verify summary stats are present in list items
        aapl_item = next(i for i in body["items"] if i["ticker"] == "AAPL")
        assert aapl_item["doc_count"] == 3
        assert aapl_item["readiness_pct"] == 66.7
        msft_item = next(i for i in body["items"] if i["ticker"] == "MSFT")
        assert msft_item["doc_count"] == 1
        assert msft_item["readiness_pct"] == 100.0

    def test_list_search_param(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.list_companies.return_value = ([], 0)

        client.get(
            "/api/v1/companies?search=apple&sector=Tech",
            headers=auth_header,
        )

        call_kwargs = mock_service.list_companies.call_args[1]
        assert call_kwargs["search"] == "apple"
        assert call_kwargs["sector"] == "Tech"

    def test_list_pagination_params(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.list_companies.return_value = ([], 0)

        resp = client.get(
            "/api/v1/companies?limit=10&offset=20&sort_by=name&sort_order=desc",
            headers=auth_header,
        )

        assert resp.status_code == 200
        call_kwargs = mock_service.list_companies.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 20
        assert call_kwargs["sort_by"] == "name"
        assert call_kwargs["sort_order"] == "desc"


# =====================================================================
# GET /api/v1/companies/{company_id}
# =====================================================================


class TestGetCompany:
    """GET /api/v1/companies/{company_id}."""

    def test_get_found(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.get_company.return_value = _make_company_obj()
        # T105 — supply rich detail summary
        mock_service.get_detail_summary.return_value = {
            "documents_summary": {
                "total": 5,
                "by_status": {"ready": 3, "error": 1, "uploaded": 1},
                "by_type": {"10-K": 3, "10-Q": 2},
                "year_range": {"min": 2021, "max": 2024},
            },
            "financials_summary": {
                "periods_available": 4,
                "year_range": {"min": 2021, "max": 2024},
            },
            "recent_sessions": [],
        }

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}",
            headers=auth_header,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "AAPL"
        # T105 — verify populated summary stats
        assert body["documents_summary"]["total"] == 5
        assert body["documents_summary"]["by_status"]["ready"] == 3
        assert body["documents_summary"]["by_type"]["10-K"] == 3
        assert body["documents_summary"]["year_range"]["min"] == 2021
        assert body["financials_summary"]["periods_available"] == 4
        assert body["financials_summary"]["year_range"]["max"] == 2024
        assert body["recent_sessions"] == []

    def test_get_not_found(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        fake_id = uuid.uuid4()
        mock_service.get_company.side_effect = NotFoundError(
            entity="Company", entity_id=str(fake_id),
        )

        resp = client.get(
            f"/api/v1/companies/{fake_id}",
            headers=auth_header,
        )

        assert resp.status_code == 404

    def test_get_invalid_uuid(
        self, client: TestClient, auth_header: dict,
    ) -> None:
        resp = client.get(
            "/api/v1/companies/not-a-uuid",
            headers=auth_header,
        )

        assert resp.status_code == 422


# =====================================================================
# PUT /api/v1/companies/{company_id}
# =====================================================================


class TestUpdateCompany:
    """PUT /api/v1/companies/{company_id}."""

    def test_update_success(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        updated = _make_company_obj(name="Apple Inc. Updated")
        mock_service.update_company.return_value = updated

        resp = client.put(
            f"/api/v1/companies/{_COMPANY_ID}",
            json={"name": "Apple Inc. Updated"},
            headers=auth_header,
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Apple Inc. Updated"
        mock_service.update_company.assert_awaited_once()

    def test_update_not_found(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.update_company.side_effect = NotFoundError(
            entity="Company", entity_id=str(_COMPANY_ID),
        )

        resp = client.put(
            f"/api/v1/companies/{_COMPANY_ID}",
            json={"name": "X"},
            headers=auth_header,
        )

        assert resp.status_code == 404


# =====================================================================
# DELETE /api/v1/companies/{company_id}
# =====================================================================


class TestDeleteCompany:
    """DELETE /api/v1/companies/{company_id}."""

    def test_delete_success(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.delete_company.return_value = None

        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}?confirm=true",
            headers=auth_header,
        )

        assert resp.status_code == 204
        mock_service.delete_company.assert_awaited_once()

    def test_delete_without_confirm(
        self, client: TestClient, auth_header: dict,
    ) -> None:
        """Missing ?confirm=true → 422 ValidationError."""
        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}",
            headers=auth_header,
        )

        assert resp.status_code == 422

    def test_delete_confirm_false(
        self, client: TestClient, auth_header: dict,
    ) -> None:
        """?confirm=false → 422."""
        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}?confirm=false",
            headers=auth_header,
        )

        assert resp.status_code == 422

    def test_delete_not_found(
        self, client: TestClient, auth_header: dict, mock_service: AsyncMock,
    ) -> None:
        mock_service.delete_company.side_effect = NotFoundError(
            entity="Company", entity_id=str(_COMPANY_ID),
        )

        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}?confirm=true",
            headers=auth_header,
        )

        assert resp.status_code == 404
