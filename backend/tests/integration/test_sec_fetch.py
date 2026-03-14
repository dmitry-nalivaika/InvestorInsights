# filepath: backend/tests/integration/test_sec_fetch.py
"""Integration tests for SEC fetch + XBRL extract flow (T313).

Verifies end-to-end:
  - SEC fetch task creates document records from filing index
  - XBRL mapper extracts structured financials from companyfacts
  - Financial service stores extracted data via upsert
  - Duplicate filings are skipped
  - Missing CIK returns error gracefully
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest

# =====================================================================
# Helpers
# =====================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_CIK = "0000320193"


def _make_company(**overrides: Any) -> MagicMock:
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _COMPANY_ID)
    obj.ticker = overrides.get("ticker", "AAPL")
    obj.name = overrides.get("name", "Apple Inc.")
    obj.cik = overrides.get("cik", _CIK)
    return obj


def _make_filing_index(count: int = 3) -> list[dict[str, Any]]:
    """Build a mock filing index with `count` 10-K filings."""
    filings = []
    for i in range(count):
        year = 2023 - i
        filings.append({
            "accession_number": f"0000320193-{year}-000001",
            "form": "10-K",
            "filing_date": f"{year}-10-30",
            "primary_document": f"aapl-{year}0930.htm",
            "description": f"10-K for fiscal year {year}",
            "filing_url": f"https://data.sec.gov/Archives/edgar/data/320193/000032019324000001/aapl-{year}0930.htm",
        })
    return filings


def _make_companyfacts_response() -> dict[str, Any]:
    """Build a minimal mock SEC companyfacts JSON response."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {
                        "USD": [
                            {
                                "val": 394328000000,
                                "end": "2023-09-30",
                                "start": "2022-10-01",
                                "form": "10-K",
                                "filed": "2023-11-02",
                                "fy": 2023,
                                "fp": "FY",
                            },
                            {
                                "val": 383285000000,
                                "end": "2022-09-24",
                                "start": "2021-09-26",
                                "form": "10-K",
                                "filed": "2022-10-28",
                                "fy": 2022,
                                "fp": "FY",
                            },
                        ],
                    },
                },
                "CostOfGoodsAndServicesSold": {
                    "label": "Cost of Goods and Services Sold",
                    "units": {
                        "USD": [
                            {
                                "val": 214137000000,
                                "end": "2023-09-30",
                                "start": "2022-10-01",
                                "form": "10-K",
                                "filed": "2023-11-02",
                                "fy": 2023,
                                "fp": "FY",
                            },
                        ],
                    },
                },
                "NetIncomeLoss": {
                    "label": "Net Income (Loss)",
                    "units": {
                        "USD": [
                            {
                                "val": 96995000000,
                                "end": "2023-09-30",
                                "start": "2022-10-01",
                                "form": "10-K",
                                "filed": "2023-11-02",
                                "fy": 2023,
                                "fp": "FY",
                            },
                        ],
                    },
                },
                "Assets": {
                    "label": "Assets",
                    "units": {
                        "USD": [
                            {
                                "val": 352583000000,
                                "end": "2023-09-30",
                                "form": "10-K",
                                "filed": "2023-11-02",
                                "fy": 2023,
                                "fp": "FY",
                            },
                        ],
                    },
                },
            },
        },
    }


# =====================================================================
# XBRL Mapper Integration
# =====================================================================


class TestXBRLExtractFlow:
    """Test the full XBRL companyfacts → mapped periods → financial service flow."""

    def test_map_company_facts_returns_structured_periods(self) -> None:
        """map_company_facts should produce structured periods from raw facts."""
        from app.xbrl.mapper import map_company_facts

        raw = _make_companyfacts_response()
        periods = map_company_facts(raw)

        assert len(periods) >= 1
        # Find the 2023 annual period
        annual_2023 = [p for p in periods if p["fiscal_year"] == 2023 and p["fiscal_quarter"] is None]
        assert len(annual_2023) >= 1

        period = annual_2023[0]
        assert "income_statement" in period
        assert "balance_sheet" in period
        assert "cash_flow" in period
        # Revenue should be mapped
        assert period["income_statement"].get("revenue") == 394328000000.0

    def test_map_company_facts_with_year_filter(self) -> None:
        """Year filters should restrict the output periods."""
        from app.xbrl.mapper import map_company_facts

        raw = _make_companyfacts_response()
        periods = map_company_facts(raw, start_year=2023, end_year=2023)

        for p in periods:
            assert p["fiscal_year"] == 2023

    def test_map_company_facts_gross_profit_fallback(self) -> None:
        """gross_profit = revenue - cost_of_revenue when not directly reported."""
        from app.xbrl.mapper import map_company_facts

        raw = _make_companyfacts_response()
        periods = map_company_facts(raw, start_year=2023, end_year=2023)

        annual_2023 = [p for p in periods if p["fiscal_year"] == 2023 and p["fiscal_quarter"] is None]
        if annual_2023:
            income = annual_2023[0]["income_statement"]
            # If revenue and cost_of_revenue are both present, gross_profit should be computed
            if "revenue" in income and "cost_of_revenue" in income:
                expected = income["revenue"] - income["cost_of_revenue"]
                assert income.get("gross_profit") == expected

    def test_map_company_facts_empty_facts(self) -> None:
        """Empty facts should return an empty list without errors."""
        from app.xbrl.mapper import map_company_facts

        result = map_company_facts({"facts": {}})
        assert result == []

    def test_map_company_facts_no_usgaap(self) -> None:
        """Facts with only IFRS (no us-gaap) return empty list."""
        from app.xbrl.mapper import map_company_facts

        result = map_company_facts({"facts": {"ifrs-full": {"SomeTag": {}}}})
        assert result == []


# =====================================================================
# Financial Service Extract & Store
# =====================================================================


class TestFinancialServiceExtractFlow:
    """Test FinancialService.extract_and_store_financials with mocked SEC client."""

    @pytest.mark.asyncio
    async def test_extract_and_store_financials(self) -> None:
        """extract_and_store_financials should fetch, map, and upsert."""
        from app.services.financial_service import FinancialService

        mock_session = AsyncMock()
        mock_sec = AsyncMock()
        mock_sec.get_company_facts.return_value = _make_companyfacts_response()

        svc = FinancialService(session=mock_session, sec_client=mock_sec)

        # Mock the repo's upsert to succeed
        with patch.object(svc._repo, "upsert", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = MagicMock()
            stored = await svc.extract_and_store_financials(
                company_id=_COMPANY_ID,
                cik=_CIK,
                start_year=2022,
                end_year=2023,
            )

        # Should have stored at least 1 period
        assert stored >= 1
        mock_sec.get_company_facts.assert_called_once_with(_CIK)
        assert mock_upsert.call_count >= 1

    @pytest.mark.asyncio
    async def test_extract_with_no_cik_returns_zero(self) -> None:
        """extract_and_store_financials should return 0 when CIK is empty."""
        from app.services.financial_service import FinancialService

        mock_session = AsyncMock()
        svc = FinancialService(session=mock_session)

        stored = await svc.extract_and_store_financials(
            company_id=_COMPANY_ID,
            cik="",
        )
        assert stored == 0

    @pytest.mark.asyncio
    async def test_extract_with_sec_failure_returns_zero(self) -> None:
        """If SEC API fails, return 0 instead of raising."""
        from app.clients.sec_client import SECEdgarError
        from app.services.financial_service import FinancialService

        mock_session = AsyncMock()
        mock_sec = AsyncMock()
        mock_sec.get_company_facts.side_effect = SECEdgarError("Network error")

        svc = FinancialService(session=mock_session, sec_client=mock_sec)

        stored = await svc.extract_and_store_financials(
            company_id=_COMPANY_ID,
            cik=_CIK,
        )
        assert stored == 0

    @pytest.mark.asyncio
    async def test_extract_upsert_handles_partial_failure(self) -> None:
        """If one period fails to store, others should still succeed."""
        from app.services.financial_service import FinancialService

        mock_session = AsyncMock()
        mock_sec = AsyncMock()
        mock_sec.get_company_facts.return_value = _make_companyfacts_response()

        svc = FinancialService(session=mock_session, sec_client=mock_sec)

        call_count = 0

        async def _upsert_with_one_failure(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Simulated DB error")
            return MagicMock()

        with patch.object(svc._repo, "upsert", side_effect=_upsert_with_one_failure):
            stored = await svc.extract_and_store_financials(
                company_id=_COMPANY_ID,
                cik=_CIK,
            )

        # At least some should have been stored (the ones that didn't fail)
        # Total = call_count - 1 (one failed)
        assert stored == call_count - 1


# =====================================================================
# SEC Fetch Task (async core logic)
# =====================================================================


class TestSECFetchAsync:
    """Test the async core of the SEC fetch task with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_fetch_creates_documents(self) -> None:
        """_fetch_sec_filings_async should create docs and dispatch ingestion."""
        from app.worker.tasks.sec_fetch_tasks import _fetch_sec_filings_async

        company = _make_company()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_id.return_value = company

        mock_doc_repo = AsyncMock()
        mock_doc_repo.get_by_company_and_period.return_value = None  # No duplicates
        mock_doc_repo.create.return_value = MagicMock(id=uuid.uuid4())

        mock_sec_client = AsyncMock()
        mock_sec_client.get_filing_index.return_value = _make_filing_index(2)
        mock_sec_client.download_filing_document.return_value = b"<html>content</html>"

        mock_storage = AsyncMock()

        # Deferred imports inside _fetch_sec_filings_async — patch at source modules
        with patch("app.db.session.get_session_factory", return_value=MagicMock(return_value=mock_session)), \
             patch("app.clients.sec_client.get_sec_client", return_value=mock_sec_client), \
             patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_company_repo), \
             patch("app.db.repositories.document_repo.DocumentRepository", return_value=mock_doc_repo), \
             patch("app.clients.storage_client.get_storage_client", return_value=mock_storage), \
             patch("app.clients.storage_client.StorageClient") as mock_sc_cls, \
             patch("app.worker.tasks.ingestion_tasks.ingest_document") as mock_ingest:
            mock_sc_cls.build_storage_key.return_value = "test/key"
            mock_ingest.delay = MagicMock()

            result = await _fetch_sec_filings_async(
                company_id=str(_COMPANY_ID),
                filing_types=["10-K"],
                year_start=2022,
                year_end=2023,
            )

        assert result["status"] == "completed"
        assert result["documents_created"] == 2
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_fetch_skips_duplicates(self) -> None:
        """Already-existing documents should be skipped."""
        from app.worker.tasks.sec_fetch_tasks import _fetch_sec_filings_async

        company = _make_company()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_id.return_value = company

        mock_doc_repo = AsyncMock()
        mock_doc_repo.get_by_company_and_period.return_value = MagicMock()  # Duplicate

        mock_sec_client = AsyncMock()
        mock_sec_client.get_filing_index.return_value = _make_filing_index(2)

        with patch("app.db.session.get_session_factory", return_value=MagicMock(return_value=mock_session)), \
             patch("app.clients.sec_client.get_sec_client", return_value=mock_sec_client), \
             patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_company_repo), \
             patch("app.db.repositories.document_repo.DocumentRepository", return_value=mock_doc_repo):
            result = await _fetch_sec_filings_async(
                company_id=str(_COMPANY_ID),
                filing_types=["10-K"],
                year_start=2022,
                year_end=2023,
            )

        assert result["status"] == "completed"
        assert result["documents_created"] == 0
        assert result["skipped"] == 2

    @pytest.mark.asyncio
    async def test_fetch_company_not_found(self) -> None:
        """Should return error when company doesn't exist."""
        from app.worker.tasks.sec_fetch_tasks import _fetch_sec_filings_async

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_id.return_value = None

        with patch("app.db.session.get_session_factory", return_value=MagicMock(return_value=mock_session)), \
             patch("app.clients.sec_client.get_sec_client"), \
             patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_company_repo), \
             patch("app.db.repositories.document_repo.DocumentRepository"):
            result = await _fetch_sec_filings_async(
                company_id=str(_COMPANY_ID),
                filing_types=["10-K"],
                year_start=2022,
                year_end=2023,
            )

        assert result["status"] == "error"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_fetch_company_no_cik(self) -> None:
        """Should return error when company has no CIK."""
        from app.worker.tasks.sec_fetch_tasks import _fetch_sec_filings_async

        company = _make_company(cik=None)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_company_repo = AsyncMock()
        mock_company_repo.get_by_id.return_value = company

        with patch("app.db.session.get_session_factory", return_value=MagicMock(return_value=mock_session)), \
             patch("app.clients.sec_client.get_sec_client"), \
             patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_company_repo), \
             patch("app.db.repositories.document_repo.DocumentRepository"):
            result = await _fetch_sec_filings_async(
                company_id=str(_COMPANY_ID),
                filing_types=["10-K"],
                year_start=2022,
                year_end=2023,
            )

        assert result["status"] == "error"
        assert "CIK" in result["message"]
