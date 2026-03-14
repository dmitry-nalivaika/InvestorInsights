# filepath: backend/tests/unit/test_company_service.py
"""Unit tests for CompanyService.

All database and SEC EDGAR interactions are mocked — these tests
exercise only the business logic in the service layer.

Covers:
  - create_company: happy path, SEC resolution, duplicate ticker (409)
  - get_company / get_company_by_ticker: found + not-found
  - list_companies: pass-through to repo
  - update_company: partial update + no-op + not-found
  - delete_company: happy path + not-found
  - _resolve_from_sec: success, TickerNotFoundError, SECEdgarError, generic error
  - _merge_create_fields: all priority/fallback combinations
"""

from __future__ import annotations

import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Set required env vars before app imports
os.environ.setdefault("API_KEY", "test-company-service")

import pytest

from app.api.middleware.error_handler import ConflictError, NotFoundError
from app.clients.sec_client import SECEdgarError, TickerNotFoundError
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company_service import CompanyService

# =====================================================================
# Helpers
# =====================================================================


def _make_company(**overrides: Any) -> MagicMock:
    """Build a mock Company ORM instance with sensible defaults."""
    company = MagicMock()
    company.id = overrides.get("id", uuid.uuid4())
    company.ticker = overrides.get("ticker", "AAPL")
    company.name = overrides.get("name", "Apple Inc.")
    company.cik = overrides.get("cik", "0000320193")
    company.sector = overrides.get("sector", "Technology")
    company.industry = overrides.get("industry")
    company.description = overrides.get("description")
    company.metadata_ = overrides.get("metadata_")
    company.created_at = overrides.get("created_at", "2024-01-01T00:00:00")
    company.updated_at = overrides.get("updated_at", "2024-01-01T00:00:00")
    return company


def _sec_metadata(ticker: str = "AAPL") -> dict[str, Any]:
    """Sample SEC EDGAR resolve_ticker response."""
    return {
        "cik": "0000320193",
        "name": "Apple Inc.",
        "ticker": ticker,
        "sic": "3571",
        "sic_description": "Electronic Computers",
        "state_of_incorporation": "CA",
        "fiscal_year_end": "0930",
        "entity_type": "operating",
        "exchanges": ["Nasdaq"],
    }


def _build_service(
    *,
    repo_mock: AsyncMock | None = None,
    sec_mock: AsyncMock | None = None,
) -> CompanyService:
    """Build a CompanyService with mocked dependencies."""
    session = AsyncMock()
    sec = sec_mock or AsyncMock()
    svc = CompanyService(session, sec_client=sec)
    if repo_mock is not None:
        svc._repo = repo_mock
    return svc


# =====================================================================
# Create
# =====================================================================


class TestCreateCompany:
    """Tests for CompanyService.create_company."""

    @pytest.mark.anyio
    async def test_create_with_sec_resolution(self) -> None:
        """Happy path: ticker resolved from SEC, company created."""
        repo = AsyncMock()
        repo.exists_by_ticker.return_value = False
        repo.create.return_value = _make_company()

        sec = AsyncMock()
        sec.resolve_ticker.return_value = _sec_metadata()

        svc = _build_service(repo_mock=repo, sec_mock=sec)
        payload = CompanyCreate(ticker="aapl")  # lowered — validator uppercases

        result = await svc.create_company(payload)

        repo.exists_by_ticker.assert_awaited_once_with("AAPL")
        sec.resolve_ticker.assert_awaited_once_with("AAPL")
        repo.create.assert_awaited_once()
        # Verify merged fields passed to repo.create
        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["ticker"] == "AAPL"
        assert call_kwargs["name"] == "Apple Inc."
        assert call_kwargs["cik"] == "0000320193"
        assert call_kwargs["metadata_"]["sec_resolved"] is True
        assert result.ticker == "AAPL"

    @pytest.mark.anyio
    async def test_create_without_sec_resolution(self) -> None:
        """SEC fails — company created with ticker as name fallback."""
        repo = AsyncMock()
        repo.exists_by_ticker.return_value = False
        repo.create.return_value = _make_company(ticker="ZZZZ", name="ZZZZ")

        sec = AsyncMock()
        sec.resolve_ticker.side_effect = TickerNotFoundError("ZZZZ")

        svc = _build_service(repo_mock=repo, sec_mock=sec)
        payload = CompanyCreate(ticker="ZZZZ")

        result = await svc.create_company(payload)

        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["name"] == "ZZZZ"  # fallback to ticker
        assert call_kwargs["cik"] is None
        assert call_kwargs["metadata_"] is None
        assert result is not None

    @pytest.mark.anyio
    async def test_create_sec_error_continues(self) -> None:
        """SEC EDGAR unreachable — company still created."""
        repo = AsyncMock()
        repo.exists_by_ticker.return_value = False
        repo.create.return_value = _make_company(ticker="MSFT", name="MSFT")

        sec = AsyncMock()
        sec.resolve_ticker.side_effect = SECEdgarError("timeout")

        svc = _build_service(repo_mock=repo, sec_mock=sec)
        payload = CompanyCreate(ticker="MSFT")

        result = await svc.create_company(payload)

        repo.create.assert_awaited_once()
        assert result is not None

    @pytest.mark.anyio
    async def test_create_caller_fields_override_sec(self) -> None:
        """Caller-provided name/sector take precedence over SEC."""
        repo = AsyncMock()
        repo.exists_by_ticker.return_value = False
        repo.create.return_value = _make_company()

        sec = AsyncMock()
        sec.resolve_ticker.return_value = _sec_metadata()

        svc = _build_service(repo_mock=repo, sec_mock=sec)
        payload = CompanyCreate(
            ticker="AAPL",
            name="My Custom Name",
            sector="My Sector",
        )

        await svc.create_company(payload)

        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["name"] == "My Custom Name"
        assert call_kwargs["sector"] == "My Sector"

    @pytest.mark.anyio
    async def test_create_duplicate_ticker_raises_conflict(self) -> None:
        """Duplicate ticker → ConflictError (409)."""
        repo = AsyncMock()
        repo.exists_by_ticker.return_value = True

        svc = _build_service(repo_mock=repo)
        payload = CompanyCreate(ticker="AAPL")

        with pytest.raises(ConflictError, match="AAPL"):
            await svc.create_company(payload)

        repo.create.assert_not_awaited()


# =====================================================================
# Read
# =====================================================================


class TestGetCompany:
    """Tests for CompanyService.get_company and get_company_by_ticker."""

    @pytest.mark.anyio
    async def test_get_by_id_found(self) -> None:
        company = _make_company()
        repo = AsyncMock()
        repo.get_by_id.return_value = company

        svc = _build_service(repo_mock=repo)
        result = await svc.get_company(company.id)

        assert result.ticker == "AAPL"
        repo.get_by_id.assert_awaited_once_with(company.id)

    @pytest.mark.anyio
    async def test_get_by_id_not_found(self) -> None:
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        svc = _build_service(repo_mock=repo)
        fake_id = uuid.uuid4()

        with pytest.raises(NotFoundError, match="Company"):
            await svc.get_company(fake_id)

    @pytest.mark.anyio
    async def test_get_by_ticker_found(self) -> None:
        company = _make_company(ticker="GOOG")
        repo = AsyncMock()
        repo.get_by_ticker.return_value = company

        svc = _build_service(repo_mock=repo)
        result = await svc.get_company_by_ticker("GOOG")

        assert result.ticker == "GOOG"

    @pytest.mark.anyio
    async def test_get_by_ticker_not_found(self) -> None:
        repo = AsyncMock()
        repo.get_by_ticker.return_value = None

        svc = _build_service(repo_mock=repo)

        with pytest.raises(NotFoundError, match="Company"):
            await svc.get_company_by_ticker("NOPE")


# =====================================================================
# List
# =====================================================================


class TestListCompanies:
    """Tests for CompanyService.list_companies."""

    @pytest.mark.anyio
    async def test_list_passes_params_to_repo(self) -> None:
        companies = [_make_company(ticker="A"), _make_company(ticker="B")]
        repo = AsyncMock()
        repo.list.return_value = (companies, 2)

        svc = _build_service(repo_mock=repo)
        items, total = await svc.list_companies(
            search="tech",
            sector="Technology",
            sort_by="name",
            sort_order="desc",
            limit=10,
            offset=5,
        )

        assert total == 2
        assert len(items) == 2
        repo.list.assert_awaited_once_with(
            search="tech",
            sector="Technology",
            sort_by="name",
            sort_order="desc",
            limit=10,
            offset=5,
        )

    @pytest.mark.anyio
    async def test_list_empty(self) -> None:
        repo = AsyncMock()
        repo.list.return_value = ([], 0)

        svc = _build_service(repo_mock=repo)
        items, total = await svc.list_companies()

        assert items == []
        assert total == 0


# =====================================================================
# Update
# =====================================================================


class TestUpdateCompany:
    """Tests for CompanyService.update_company."""

    @pytest.mark.anyio
    async def test_update_partial(self) -> None:
        company = _make_company()
        repo = AsyncMock()
        repo.get_by_id.return_value = company
        repo.update.return_value = company

        svc = _build_service(repo_mock=repo)
        payload = CompanyUpdate(name="New Name")

        await svc.update_company(company.id, payload)

        repo.update.assert_awaited_once()
        call_kwargs = repo.update.call_args[1]
        assert "name" in call_kwargs

    @pytest.mark.anyio
    async def test_update_noop_when_no_fields(self) -> None:
        """Empty update payload → no repo.update call."""
        company = _make_company()
        repo = AsyncMock()
        repo.get_by_id.return_value = company

        svc = _build_service(repo_mock=repo)
        payload = CompanyUpdate()  # nothing set

        result = await svc.update_company(company.id, payload)

        repo.update.assert_not_awaited()
        assert result is company

    @pytest.mark.anyio
    async def test_update_not_found(self) -> None:
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        svc = _build_service(repo_mock=repo)
        payload = CompanyUpdate(name="X")

        with pytest.raises(NotFoundError):
            await svc.update_company(uuid.uuid4(), payload)


# =====================================================================
# Delete
# =====================================================================


class TestDeleteCompany:
    """Tests for CompanyService.delete_company."""

    @pytest.mark.anyio
    async def test_delete_found(self) -> None:
        company = _make_company()
        repo = AsyncMock()
        repo.get_by_id.return_value = company

        svc = _build_service(repo_mock=repo)
        await svc.delete_company(company.id)

        repo.delete.assert_awaited_once_with(company)

    @pytest.mark.anyio
    async def test_delete_not_found(self) -> None:
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        svc = _build_service(repo_mock=repo)

        with pytest.raises(NotFoundError):
            await svc.delete_company(uuid.uuid4())

        repo.delete.assert_not_awaited()


# =====================================================================
# SEC resolution (private)
# =====================================================================


class TestResolveFromSec:
    """Tests for CompanyService._resolve_from_sec."""

    @pytest.mark.anyio
    async def test_resolve_success(self) -> None:
        sec = AsyncMock()
        sec.resolve_ticker.return_value = _sec_metadata("AAPL")

        svc = _build_service(sec_mock=sec)
        result = await svc._resolve_from_sec("AAPL")

        assert result is not None
        assert result["cik"] == "0000320193"

    @pytest.mark.anyio
    async def test_resolve_ticker_not_found(self) -> None:
        sec = AsyncMock()
        sec.resolve_ticker.side_effect = TickerNotFoundError("NOPE")

        svc = _build_service(sec_mock=sec)
        result = await svc._resolve_from_sec("NOPE")

        assert result is None

    @pytest.mark.anyio
    async def test_resolve_sec_error(self) -> None:
        sec = AsyncMock()
        sec.resolve_ticker.side_effect = SECEdgarError("server error", 500)

        svc = _build_service(sec_mock=sec)
        result = await svc._resolve_from_sec("AAPL")

        assert result is None

    @pytest.mark.anyio
    async def test_resolve_generic_exception(self) -> None:
        sec = AsyncMock()
        sec.resolve_ticker.side_effect = RuntimeError("unexpected")

        svc = _build_service(sec_mock=sec)
        result = await svc._resolve_from_sec("AAPL")

        assert result is None


# =====================================================================
# Field merging (private)
# =====================================================================


class TestMergeCreateFields:
    """Tests for CompanyService._merge_create_fields."""

    def test_merge_with_sec_metadata(self) -> None:
        payload = CompanyCreate(ticker="AAPL")
        sec = _sec_metadata()

        result = CompanyService._merge_create_fields(payload, sec)

        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["cik"] == "0000320193"
        assert result["sector"] == "Electronic Computers"
        assert result["metadata_"]["sec_resolved"] is True
        assert result["metadata_"]["sic"] == "3571"

    def test_merge_without_sec_metadata(self) -> None:
        payload = CompanyCreate(ticker="ZZZZ")

        result = CompanyService._merge_create_fields(payload, None)

        assert result["ticker"] == "ZZZZ"
        assert result["name"] == "ZZZZ"  # fallback to ticker
        assert result["cik"] is None
        assert result["sector"] is None
        assert result["metadata_"] is None

    def test_merge_caller_overrides_sec(self) -> None:
        payload = CompanyCreate(
            ticker="AAPL",
            name="Custom Name",
            cik="9999999999",
            sector="Custom Sector",
            industry="Custom Industry",
        )
        sec = _sec_metadata()

        result = CompanyService._merge_create_fields(payload, sec)

        assert result["name"] == "Custom Name"
        assert result["cik"] == "9999999999"
        assert result["sector"] == "Custom Sector"
        assert result["industry"] == "Custom Industry"
        # SEC metadata still stored
        assert result["metadata_"]["sec_resolved"] is True

    def test_merge_partial_caller_partial_sec(self) -> None:
        """Caller provides name, SEC fills in CIK and sector."""
        payload = CompanyCreate(ticker="AAPL", name="My Apple")
        sec = _sec_metadata()

        result = CompanyService._merge_create_fields(payload, sec)

        assert result["name"] == "My Apple"          # caller wins
        assert result["cik"] == "0000320193"          # from SEC
        assert result["sector"] == "Electronic Computers"  # from SEC
