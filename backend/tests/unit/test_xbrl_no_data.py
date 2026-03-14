# filepath: backend/tests/unit/test_xbrl_no_data.py
"""Unit tests for no-XBRL-data handling (T820).

Verifies:
  - _try_extract_xbrl_financials skips when company has no CIK
  - _try_extract_xbrl_financials logs warning when no XBRL data available
  - _try_extract_xbrl_financials never raises, even on unexpected errors
  - _try_extract_xbrl_financials returns periods_stored on success
  - Ingestion task result includes XBRL metadata
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Set env vars BEFORE any app imports
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest

from app.worker.tasks.ingestion_tasks import _try_extract_xbrl_financials

# Patch target: the import inside _try_extract_xbrl_financials does
# `from app.services.financial_service import FinancialService`
_PATCH_FINANCIAL_SERVICE = "app.services.financial_service.FinancialService"


# =====================================================================
# Helpers
# =====================================================================

COMPANY_ID = str(uuid.uuid4())
DOCUMENT_ID = str(uuid.uuid4())
CIK = "0001234567"


# =====================================================================
# _try_extract_xbrl_financials — no CIK
# =====================================================================


class TestTryExtractXBRLNoCIK:
    """When the company has no CIK, XBRL extraction is skipped."""

    @pytest.mark.asyncio
    async def test_no_cik_skips_extraction(self) -> None:
        """Returns xbrl_attempted=False when CIK is None."""
        result = await _try_extract_xbrl_financials(
            document_id=DOCUMENT_ID,
            company_id=COMPANY_ID,
            cik=None,
            fiscal_year=2024,
            session=AsyncMock(),
        )

        assert result["xbrl_attempted"] is False
        assert result["xbrl_periods_stored"] == 0
        assert "no CIK" in result["xbrl_warning"]

    @pytest.mark.asyncio
    async def test_empty_cik_skips_extraction(self) -> None:
        """Returns xbrl_attempted=False when CIK is empty string."""
        result = await _try_extract_xbrl_financials(
            document_id=DOCUMENT_ID,
            company_id=COMPANY_ID,
            cik="",
            fiscal_year=2024,
            session=AsyncMock(),
        )

        assert result["xbrl_attempted"] is False
        assert result["xbrl_periods_stored"] == 0


# =====================================================================
# _try_extract_xbrl_financials — no XBRL data available
# =====================================================================


class TestTryExtractXBRLNoData:
    """When SEC returns no XBRL data, a warning is logged but ingestion is unaffected."""

    @pytest.mark.asyncio
    async def test_no_xbrl_data_returns_warning(self) -> None:
        """Returns xbrl_attempted=True, 0 periods, and a warning."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(return_value=0)
            MockFinSvc.return_value = mock_svc_instance

            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )

        assert result["xbrl_attempted"] is True
        assert result["xbrl_periods_stored"] == 0
        assert result["xbrl_warning"] is not None
        assert "No XBRL data" in result["xbrl_warning"]

    @pytest.mark.asyncio
    async def test_no_xbrl_data_does_not_raise(self) -> None:
        """The function never raises, even if the service returns 0."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(return_value=0)
            MockFinSvc.return_value = mock_svc_instance

            # Should not raise
            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )
            assert isinstance(result, dict)


# =====================================================================
# _try_extract_xbrl_financials — SEC fetch/extraction failure
# =====================================================================


class TestTryExtractXBRLFailure:
    """When XBRL extraction fails (SEC down, parse error, etc.), ingestion is unaffected."""

    @pytest.mark.asyncio
    async def test_sec_fetch_failure_returns_warning(self) -> None:
        """SEC API error → warning, never raises."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(
                side_effect=ConnectionError("SEC EDGAR unreachable"),
            )
            MockFinSvc.return_value = mock_svc_instance

            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )

        assert result["xbrl_attempted"] is True
        assert result["xbrl_periods_stored"] == 0
        assert "failed" in result["xbrl_warning"].lower()
        assert "SEC EDGAR unreachable" in result["xbrl_warning"]

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_warning(self) -> None:
        """Any unexpected error → warning, never raises."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(
                side_effect=RuntimeError("Something unexpected"),
            )
            MockFinSvc.return_value = mock_svc_instance

            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )

        assert result["xbrl_attempted"] is True
        assert result["xbrl_periods_stored"] == 0
        assert "Something unexpected" in result["xbrl_warning"]

    @pytest.mark.asyncio
    async def test_db_error_during_upsert_returns_warning(self) -> None:
        """Database error during XBRL upsert → warning, not crash."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(
                side_effect=Exception("UNIQUE constraint violation"),
            )
            MockFinSvc.return_value = mock_svc_instance

            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )

        assert result["xbrl_attempted"] is True
        assert result["xbrl_periods_stored"] == 0
        assert "UNIQUE constraint" in result["xbrl_warning"]


# =====================================================================
# _try_extract_xbrl_financials — successful extraction
# =====================================================================


class TestTryExtractXBRLSuccess:
    """When XBRL extraction succeeds, periods_stored is returned."""

    @pytest.mark.asyncio
    async def test_successful_extraction_returns_count(self) -> None:
        """Successful extraction returns xbrl_periods_stored > 0."""
        mock_session = AsyncMock()

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(return_value=3)
            MockFinSvc.return_value = mock_svc_instance

            result = await _try_extract_xbrl_financials(
                document_id=DOCUMENT_ID,
                company_id=COMPANY_ID,
                cik=CIK,
                fiscal_year=2024,
                session=mock_session,
            )

        assert result["xbrl_attempted"] is True
        assert result["xbrl_periods_stored"] == 3
        assert result["xbrl_warning"] is None

    @pytest.mark.asyncio
    async def test_passes_document_id_and_year_to_service(self) -> None:
        """The document_id and fiscal_year are forwarded to the service."""
        mock_session = AsyncMock()
        doc_id = str(uuid.uuid4())
        comp_id = str(uuid.uuid4())

        with patch(
            _PATCH_FINANCIAL_SERVICE
        ) as MockFinSvc:
            mock_svc_instance = AsyncMock()
            mock_svc_instance.extract_and_store_financials = AsyncMock(return_value=1)
            MockFinSvc.return_value = mock_svc_instance

            await _try_extract_xbrl_financials(
                document_id=doc_id,
                company_id=comp_id,
                cik="0009999999",
                fiscal_year=2023,
                session=mock_session,
            )

            call_kwargs = mock_svc_instance.extract_and_store_financials.call_args
            assert str(call_kwargs.kwargs["company_id"]) == comp_id
            assert str(call_kwargs.kwargs["document_id"]) == doc_id
            assert call_kwargs.kwargs["cik"] == "0009999999"
            assert call_kwargs.kwargs["start_year"] == 2023
            assert call_kwargs.kwargs["end_year"] == 2023


# =====================================================================
# Integration: XBRL result keys in ingestion response
# =====================================================================


class TestXBRLResultKeys:
    """Verify the xbrl_* keys are present and well-typed."""

    @pytest.mark.asyncio
    async def test_result_has_all_xbrl_keys(self) -> None:
        """All three xbrl_* keys must be present in every result."""
        result = await _try_extract_xbrl_financials(
            document_id=DOCUMENT_ID,
            company_id=COMPANY_ID,
            cik=None,
            fiscal_year=2024,
            session=AsyncMock(),
        )

        assert "xbrl_attempted" in result
        assert "xbrl_periods_stored" in result
        assert "xbrl_warning" in result
        assert isinstance(result["xbrl_attempted"], bool)
        assert isinstance(result["xbrl_periods_stored"], int)
