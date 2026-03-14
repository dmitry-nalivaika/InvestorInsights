# filepath: backend/tests/e2e/test_e2e_journeys.py
"""End-to-end journey tests (T801).

These tests exercise the full HTTP path through the API layer, validating
that multi-step user workflows succeed end-to-end with correct status codes,
response payloads, and state transitions.

All services are mocked via FastAPI dependency overrides — no real DB, Qdrant,
or LLM connection is needed.  The goal is to verify the *API contract* across
a sequence of related requests, not to test individual service methods.

Journey 1: Company lifecycle (register → list → detail → update → delete)
Journey 2: Upload + Chat (create company → upload document → list docs → chat)
Journey 3: Analysis (create company → create profile → run analysis → compare)
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Env vars must be set BEFORE any app imports.
# Use os.environ[] (not setdefault) so these override values set by
# integration test conftest.py when running together in the same process.
os.environ["API_KEY"] = "test-e2e-key"
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest
from fastapi.testclient import TestClient

from app.api.middleware.error_handler import ConflictError, NotFoundError
from app.models.criterion import ComparisonOp, CriteriaCategory
from app.models.document import DocStatus, DocType
from app.services.analysis_service import AnalysisService
from app.services.chat_service import ChatService
from app.services.company_service import CompanyService
from app.services.document_service import DocumentService


# =====================================================================
# Constants & helpers
# =====================================================================

_NOW = datetime(2024, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_COMPANY_ID_2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
_DOC_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_PROFILE_ID = uuid.UUID("aaaa1111-1111-1111-1111-111111111111")
_RESULT_ID = uuid.UUID("bbbb2222-2222-2222-2222-222222222222")
_RESULT_ID_2 = uuid.UUID("bbbb3333-3333-3333-3333-333333333333")
_SESSION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_MSG_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _mock_company(**overrides: Any) -> MagicMock:
    """Build a mock that looks like a Company ORM object."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _COMPANY_ID)
    obj.ticker = overrides.get("ticker", "AAPL")
    obj.name = overrides.get("name", "Apple Inc.")
    obj.cik = overrides.get("cik", "0000320193")
    obj.sector = overrides.get("sector", "Technology")
    obj.industry = overrides.get("industry", "Consumer Electronics")
    obj.description = overrides.get("description", None)
    obj.metadata_ = overrides.get("metadata_", None)
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    return obj


def _mock_company_list_item(**overrides: Any) -> MagicMock:
    """Mock for list items with doc count, etc."""
    obj = _mock_company(**overrides)
    obj.doc_count = overrides.get("doc_count", 3)
    obj.latest_filing_date = overrides.get("latest_filing_date", date(2024, 3, 15))
    obj.readiness_pct = overrides.get("readiness_pct", 0.67)
    return obj


def _mock_document(**overrides: Any) -> MagicMock:
    """Build a mock that looks like a Document ORM object."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _DOC_ID)
    obj.company_id = overrides.get("company_id", _COMPANY_ID)
    obj.doc_type = overrides.get("doc_type", DocType.TEN_K)
    obj.fiscal_year = overrides.get("fiscal_year", 2023)
    obj.fiscal_quarter = overrides.get("fiscal_quarter", None)
    obj.filing_date = overrides.get("filing_date", date(2024, 2, 2))
    obj.period_end_date = overrides.get("period_end_date", date(2023, 12, 31))
    obj.sec_accession = overrides.get("sec_accession", "0000320193-24-000010")
    obj.source_url = overrides.get("source_url", None)
    obj.storage_key = overrides.get("storage_key", f"companies/{_COMPANY_ID}/10-K/2023/filing.pdf")
    obj.file_size_bytes = overrides.get("file_size_bytes", 1_500_000)
    obj.page_count = overrides.get("page_count", 120)
    obj.status = overrides.get("status", DocStatus.UPLOADED)
    obj.error_message = overrides.get("error_message", None)
    obj.processing_started_at = overrides.get("processing_started_at", None)
    obj.processing_completed_at = overrides.get("processing_completed_at", None)
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    return obj


def _mock_session(**overrides: Any) -> MagicMock:
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _SESSION_ID)
    obj.company_id = overrides.get("company_id", _COMPANY_ID)
    obj.title = overrides.get("title", "Apple Revenue Discussion")
    obj.message_count = overrides.get("message_count", 0)
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    return obj


def _mock_profile(**overrides: Any) -> MagicMock:
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _PROFILE_ID)
    obj.name = overrides.get("name", "Quality Value")
    obj.description = overrides.get("description", "Balanced profile")
    obj.is_default = overrides.get("is_default", True)
    obj.version = overrides.get("version", 1)
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    obj.criteria = overrides.get("criteria", [])
    return obj


def _mock_criterion(**overrides: Any) -> MagicMock:
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", uuid.uuid4())
    obj.profile_id = overrides.get("profile_id", _PROFILE_ID)
    obj.name = overrides.get("name", "Gross Margin > 40%")
    obj.category = overrides.get("category", CriteriaCategory.PROFITABILITY)
    obj.description = overrides.get("description", None)
    obj.formula = overrides.get("formula", "gross_margin")
    obj.is_custom_formula = overrides.get("is_custom_formula", False)
    obj.comparison = overrides.get("comparison", ComparisonOp.GTE)
    obj.threshold_value = overrides.get("threshold_value", Decimal("0.40"))
    obj.threshold_low = overrides.get("threshold_low", None)
    obj.threshold_high = overrides.get("threshold_high", None)
    obj.weight = overrides.get("weight", Decimal("2.0"))
    obj.lookback_years = overrides.get("lookback_years", 5)
    obj.enabled = overrides.get("enabled", True)
    obj.sort_order = overrides.get("sort_order", 0)
    obj.created_at = overrides.get("created_at", _NOW)
    return obj


def _mock_result(
    result_id: uuid.UUID = _RESULT_ID,
    company_id: uuid.UUID = _COMPANY_ID,
    **overrides: Any,
) -> MagicMock:
    obj = MagicMock(spec=[])
    obj.id = result_id
    obj.company_id = company_id
    obj.profile_id = overrides.get("profile_id", _PROFILE_ID)
    obj.profile_version = overrides.get("profile_version", 1)
    obj.run_at = overrides.get("run_at", _NOW)
    obj.overall_score = overrides.get("overall_score", Decimal("4.0"))
    obj.max_score = overrides.get("max_score", Decimal("6.0"))
    obj.pct_score = overrides.get("pct_score", Decimal("66.67"))
    obj.criteria_count = overrides.get("criteria_count", 3)
    obj.passed_count = overrides.get("passed_count", 2)
    obj.failed_count = overrides.get("failed_count", 1)
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
            "trend": "stable",
        },
    ])
    obj.summary = overrides.get("summary", "Company has strong profitability.")
    obj.created_at = overrides.get("created_at", _NOW)
    # For company info on result
    obj.company = _mock_company(id=company_id)
    return obj


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture(scope="session")
def app():
    """Shared FastAPI app for e2e tests.

    Clears the cached Settings singleton so env vars set at the top of
    this module (API_KEY=test-e2e-key, etc.) are picked up even when
    integration tests ran first in the same process.
    """
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


@pytest.fixture()
def auth_header() -> dict[str, str]:
    return {"X-API-Key": "test-e2e-key"}


@pytest.fixture()
def mock_company_svc() -> AsyncMock:
    svc = AsyncMock(spec=CompanyService)
    svc.get_bulk_summary_stats.return_value = {}
    svc.get_detail_summary.return_value = {
        "documents_summary": {
            "total": 0, "by_status": {}, "by_type": {},
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
def mock_doc_svc(mock_db_session: AsyncMock) -> AsyncMock:
    svc = AsyncMock(spec=DocumentService)
    # The upload endpoint accesses service._session to build a CompanyRepository
    svc._session = mock_db_session
    return svc


@pytest.fixture()
def mock_analysis_svc() -> AsyncMock:
    return AsyncMock(spec=AnalysisService)


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Mock async database session for endpoints that use DbSessionDep directly."""
    return AsyncMock()


@pytest.fixture()
def e2e_client(
    app,
    mock_company_svc: AsyncMock,
    mock_doc_svc: AsyncMock,
    mock_analysis_svc: AsyncMock,
    mock_db_session: AsyncMock,
) -> TestClient:
    """TestClient with ALL service dependencies overridden."""
    from app.api.analysis import _get_analysis_service
    from app.api.companies import _get_company_service
    from app.api.documents import _get_document_service
    from app.dependencies import get_db

    app.dependency_overrides[_get_company_service] = lambda: mock_company_svc
    app.dependency_overrides[_get_document_service] = lambda: mock_doc_svc
    app.dependency_overrides[_get_analysis_service] = lambda: mock_analysis_svc
    app.dependency_overrides[get_db] = lambda: mock_db_session

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


# =====================================================================
# Journey 1: Company lifecycle
#
# Register AAPL → list companies → get detail → update description →
# list again (verify update) → delete → confirm gone (404)
# =====================================================================


class TestCompanyJourney:
    """Full company lifecycle: create → list → detail → update → delete."""

    def test_register_and_list(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_company_svc: AsyncMock,
    ) -> None:
        """Register a company and verify it appears in the list."""
        # Step 1: Create company
        company = _mock_company()
        mock_company_svc.create_company.return_value = company

        resp = e2e_client.post(
            "/api/v1/companies",
            json={"ticker": "AAPL"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert body["name"] == "Apple Inc."
        assert body["cik"] == "0000320193"
        company_id = body["id"]

        # Step 2: List companies — should contain the new company
        mock_company_svc.list_companies.return_value = (
            [_mock_company_list_item()], 1,
        )
        mock_company_svc.get_bulk_summary_stats.return_value = {
            _COMPANY_ID: {"doc_count": 3, "latest_filing_date": date(2024, 3, 15), "readiness_pct": 0.67},
        }

        resp = e2e_client.get("/api/v1/companies", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["ticker"] == "AAPL"

    def test_detail_and_update(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_company_svc: AsyncMock,
    ) -> None:
        """Get company detail, update description, verify change."""
        # Step 1: Get detail
        company = _mock_company()
        mock_company_svc.get_company.return_value = company

        resp = e2e_client.get(
            f"/api/v1/companies/{_COMPANY_ID}", headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

        # Step 2: Update description
        updated = _mock_company(description="Global technology leader")
        mock_company_svc.update_company.return_value = updated

        resp = e2e_client.put(
            f"/api/v1/companies/{_COMPANY_ID}",
            json={"description": "Global technology leader"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Global technology leader"

    def test_delete_flow(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_company_svc: AsyncMock,
    ) -> None:
        """Delete company and confirm 404 on subsequent lookup."""
        # Step 1: Delete (must pass ?confirm=true)
        mock_company_svc.delete_company.return_value = None

        resp = e2e_client.delete(
            f"/api/v1/companies/{_COMPANY_ID}?confirm=true",
            headers=auth_header,
        )
        assert resp.status_code == 204

        # Step 2: Attempt to get → 404
        mock_company_svc.get_company.side_effect = NotFoundError(
            "Company", entity_id=str(_COMPANY_ID),
        )

        resp = e2e_client.get(
            f"/api/v1/companies/{_COMPANY_ID}", headers=auth_header,
        )
        assert resp.status_code == 404

    def test_duplicate_ticker_rejected(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_company_svc: AsyncMock,
    ) -> None:
        """Registering the same ticker twice returns 409."""
        mock_company_svc.create_company.side_effect = ConflictError(
            "Company with ticker 'AAPL' already exists",
        )

        resp = e2e_client.post(
            "/api/v1/companies",
            json={"ticker": "AAPL"},
            headers=auth_header,
        )
        assert resp.status_code == 409

    def test_delete_without_confirm(
        self,
        e2e_client: TestClient,
        auth_header: dict,
    ) -> None:
        """Deleting without ?confirm=true fails with 422."""
        resp = e2e_client.delete(
            f"/api/v1/companies/{_COMPANY_ID}",
            headers=auth_header,
        )
        assert resp.status_code == 422


# =====================================================================
# Journey 2: Upload + Chat
#
# Create company → upload 10-K → list documents → verify doc state →
# POST chat message → receive SSE stream
# =====================================================================


class TestUploadChatJourney:
    """Upload a filing and then chat against the company's documents."""

    def test_upload_document(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_doc_svc: AsyncMock,
    ) -> None:
        """Upload a 10-K PDF and verify 202 + document ID returned."""
        doc = _mock_document()
        mock_doc_svc.upload_document.return_value = doc

        # CompanyRepository is imported inside the endpoint function body,
        # so we must patch at the source module.
        with patch(
            "app.db.repositories.company_repo.CompanyRepository"
        ) as MockCompanyRepo:
            repo_inst = AsyncMock()
            repo_inst.get_by_id.return_value = _mock_company()
            MockCompanyRepo.return_value = repo_inst

            # Patch Celery dispatch to avoid broker connection
            with patch(
                "app.worker.tasks.ingestion_tasks.ingest_document",
                create=True,
            ) as mock_ingest:
                mock_ingest.delay = MagicMock()

                resp = e2e_client.post(
                    f"/api/v1/companies/{_COMPANY_ID}/documents",
                    headers=auth_header,
                    files={"file": ("10K-2023.pdf", b"%PDF-1.5 fake content", "application/pdf")},
                    data={
                        "doc_type": "10-K",
                        "fiscal_year": "2023",
                        "filing_date": "2024-02-02",
                        "period_end_date": "2023-12-31",
                    },
                )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "uploaded"
        assert "document_id" in body

    def test_list_documents_after_upload(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_doc_svc: AsyncMock,
    ) -> None:
        """List documents returns the uploaded filing."""
        doc = _mock_document(status=DocStatus.READY)
        mock_doc_svc.list_documents.return_value = ([doc], 1)

        resp = e2e_client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["doc_type"] == "10-K"

    def test_chat_returns_sse_stream(
        self,
        e2e_client: TestClient,
        auth_header: dict,
    ) -> None:
        """POST chat message returns an SSE stream with session, sources, tokens, done."""
        # We need to mock several layers for chat: company lookup, doc check,
        # chat service, and the chat agent.
        mock_session = _mock_session()

        with (
            patch("app.api.chat.CompanyRepository") as MockCompRepo,
            patch("app.api.chat.DocumentRepository") as MockDocRepo,
            patch("app.api.chat.ChatService") as MockChatSvcCls,
            patch("app.api.chat.CompanyChatAgent") as MockAgentCls,
        ):
            # Company exists
            comp_repo = AsyncMock()
            comp_repo.get_by_id.return_value = _mock_company()
            MockCompRepo.return_value = comp_repo

            # One READY document
            doc_repo = AsyncMock()
            ready_doc = _mock_document(status=DocStatus.READY)
            doc_repo.list_by_company.return_value = ([ready_doc], 1)
            MockDocRepo.return_value = doc_repo

            # Chat service: create session, add message, get history
            chat_svc = AsyncMock()
            chat_svc.create_session.return_value = mock_session
            mock_user_msg = MagicMock()
            mock_user_msg.id = _MSG_ID
            chat_svc.add_user_message.return_value = mock_user_msg
            chat_svc.get_conversation_history.return_value = [
                {"role": "user", "content": "What is Apple's revenue?"},
            ]
            chat_svc.auto_generate_title.return_value = "Apple Revenue Discussion"
            # The streaming function creates a second ChatService(db) to persist
            # the assistant message — same mock class, so configure it here.
            mock_assistant_msg = MagicMock()
            mock_assistant_msg.id = uuid.uuid4()
            chat_svc.add_assistant_message.return_value = mock_assistant_msg
            MockChatSvcCls.return_value = chat_svc

            # Chat agent streams events
            from app.rag.chat_agent import DoneEvent, SourcesEvent, TokenEvent

            async def _fake_generate(*args, **kwargs):
                yield SourcesEvent(sources=[])
                yield TokenEvent(token="Apple's ")
                yield TokenEvent(token="revenue was $394B.")
                yield DoneEvent(
                    full_text="Apple's revenue was $394B.",
                    token_count=8,
                    citations=[],
                    model="gpt-4o-mini",
                )

            agent_inst = MagicMock()
            agent_inst.generate_response = _fake_generate
            MockAgentCls.return_value = agent_inst

            resp = e2e_client.post(
                f"/api/v1/companies/{_COMPANY_ID}/chat",
                json={"message": "What is Apple's revenue?"},
                headers=auth_header,
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        # SSE stream should contain expected event types
        assert "event: session" in body
        assert "event: sources" in body
        assert "event: token" in body
        assert "event: done" in body


# =====================================================================
# Journey 3: Analysis
#
# Create profile → run analysis → view results → compare two companies
# =====================================================================


class TestAnalysisJourney:
    """Profile creation → analysis execution → comparison."""

    def test_create_profile_and_run_analysis(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_analysis_svc: AsyncMock,
    ) -> None:
        """Create a profile, run analysis, and verify result structure."""
        # Step 1: Create profile
        criterion = _mock_criterion()
        profile = _mock_profile(criteria=[criterion])
        mock_analysis_svc.create_profile.return_value = profile

        resp = e2e_client.post(
            "/api/v1/analysis/profiles",
            json={
                "name": "Quality Value",
                "description": "Balanced profile",
                "criteria": [
                    {
                        "name": "Gross Margin > 40%",
                        "category": "profitability",
                        "formula": "gross_margin",
                        "comparison": ">=",
                        "threshold_value": "0.40",
                        "weight": "2.0",
                    },
                ],
            },
            headers=auth_header,
        )
        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        # Step 2: Run analysis
        result = _mock_result()
        mock_analysis_svc.run_analysis.return_value = [result]

        resp = e2e_client.post(
            "/api/v1/analysis/run",
            json={
                "company_ids": [str(_COMPANY_ID)],
                "profile_id": profile_id,
            },
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert float(data["results"][0]["pct_score"]) > 0

    def test_list_and_get_results(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_analysis_svc: AsyncMock,
    ) -> None:
        """List analysis results and retrieve a single result."""
        result = _mock_result()
        mock_analysis_svc.list_results.return_value = ([result], 1)

        resp = e2e_client.get(
            "/api/v1/analysis/results",
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Get single result
        mock_analysis_svc.get_result.return_value = result

        resp = e2e_client.get(
            f"/api/v1/analysis/results/{_RESULT_ID}",
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(_RESULT_ID)

    def test_compare_companies(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_analysis_svc: AsyncMock,
    ) -> None:
        """Compare two companies and verify ranked output."""
        result_a = _mock_result(
            result_id=_RESULT_ID,
            company_id=_COMPANY_ID,
            pct_score=Decimal("80.00"),
            overall_score=Decimal("4.8"),
            max_score=Decimal("6.0"),
        )
        result_b = _mock_result(
            result_id=_RESULT_ID_2,
            company_id=_COMPANY_ID_2,
            pct_score=Decimal("55.00"),
            overall_score=Decimal("3.3"),
            max_score=Decimal("6.0"),
        )
        # Mock company on result_b
        result_b.company = _mock_company(id=_COMPANY_ID_2, ticker="MSFT", name="Microsoft Corp.")

        # compare_companies returns a dict consumed by _build_comparison_response
        mock_analysis_svc.compare_companies.return_value = {
            "profile_id": _PROFILE_ID,
            "profile_name": "Quality Value",
            "companies_count": 2,
            "criteria_names": ["Gross Margin > 40%"],
            "ranked_results": [result_a, result_b],
            "no_data_ids": set(),
        }

        resp = e2e_client.post(
            "/api/v1/analysis/compare",
            json={
                "company_ids": [str(_COMPANY_ID), str(_COMPANY_ID_2)],
                "profile_id": str(_PROFILE_ID),
            },
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["companies_count"] == 2
        # Rankings should be ordered by score descending
        rankings = data["rankings"]
        assert len(rankings) == 2
        assert float(rankings[0]["pct_score"]) >= float(rankings[1]["pct_score"])

    def test_analysis_with_nonexistent_profile(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_analysis_svc: AsyncMock,
    ) -> None:
        """Running analysis with unknown profile returns 404."""
        fake_id = uuid.uuid4()
        mock_analysis_svc.run_analysis.side_effect = NotFoundError(
            "Profile", entity_id=str(fake_id),
        )

        resp = e2e_client.post(
            "/api/v1/analysis/run",
            json={
                "company_ids": [str(_COMPANY_ID)],
                "profile_id": str(fake_id),
            },
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_profile_crud_lifecycle(
        self,
        e2e_client: TestClient,
        auth_header: dict,
        mock_analysis_svc: AsyncMock,
    ) -> None:
        """Create → update → delete profile lifecycle."""
        criterion = _mock_criterion()
        profile = _mock_profile(criteria=[criterion])

        # Create
        mock_analysis_svc.create_profile.return_value = profile
        resp = e2e_client.post(
            "/api/v1/analysis/profiles",
            json={
                "name": "Test Profile",
                "criteria": [{
                    "name": "ROE",
                    "category": "profitability",
                    "formula": "net_income / equity",
                    "comparison": ">=",
                    "threshold_value": "0.15",
                }],
            },
            headers=auth_header,
        )
        assert resp.status_code == 201

        # Update
        updated = _mock_profile(name="Updated Profile", criteria=[criterion])
        mock_analysis_svc.update_profile.return_value = updated
        resp = e2e_client.put(
            f"/api/v1/analysis/profiles/{_PROFILE_ID}",
            json={"name": "Updated Profile"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Profile"

        # Delete
        mock_analysis_svc.delete_profile.return_value = None
        resp = e2e_client.delete(
            f"/api/v1/analysis/profiles/{_PROFILE_ID}",
            headers=auth_header,
        )
        assert resp.status_code == 204

    def test_formulas_endpoint(
        self,
        e2e_client: TestClient,
        auth_header: dict,
    ) -> None:
        """GET /analysis/formulas returns 25+ built-in formulas."""
        resp = e2e_client.get(
            "/api/v1/analysis/formulas", headers=auth_header,
        )
        assert resp.status_code == 200
        formulas = resp.json()["formulas"]
        assert len(formulas) >= 25


# =====================================================================
# Cross-cutting: auth enforcement throughout journeys
# =====================================================================


class TestAuthEnforcement:
    """Verify all journey endpoints require authentication."""

    @pytest.fixture()
    def unauth_client(self, app) -> TestClient:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/companies"),
            ("GET", "/api/v1/companies"),
            ("GET", f"/api/v1/companies/{_COMPANY_ID}"),
            ("PUT", f"/api/v1/companies/{_COMPANY_ID}"),
            ("DELETE", f"/api/v1/companies/{_COMPANY_ID}?confirm=true"),
            ("GET", f"/api/v1/companies/{_COMPANY_ID}/documents"),
            ("POST", f"/api/v1/companies/{_COMPANY_ID}/chat"),
            ("POST", "/api/v1/analysis/profiles"),
            ("GET", "/api/v1/analysis/profiles"),
            ("POST", "/api/v1/analysis/run"),
            ("POST", "/api/v1/analysis/compare"),
            ("GET", "/api/v1/analysis/results"),
            ("GET", "/api/v1/analysis/formulas"),
        ],
    )
    def test_returns_401_without_api_key(
        self, unauth_client: TestClient, method: str, path: str,
    ) -> None:
        resp = unauth_client.request(method, path)
        assert resp.status_code == 401

class TestHealthCheck:
    """Verify health endpoint is accessible without auth."""

    def test_health_no_auth(self, app) -> None:
        with TestClient(app) as c:
            resp = c.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        # In test env with no real backends, status may be unhealthy —
        # the key assertion is that the endpoint is reachable without auth.
        assert body["status"] in ("healthy", "degraded", "unhealthy")
