# filepath: backend/tests/integration/test_documents_api.py
"""Integration tests for Document API routes.

Tests the full HTTP path: request -> FastAPI routing -> validation ->
response serialization -> status codes.

The DocumentService is injected via dependency override so we can
test the API layer without a real database or blob storage.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest
from fastapi.testclient import TestClient  # noqa: TC002

from app.api.middleware.error_handler import ConflictError, NotFoundError, ValidationError
from app.models.document import DocStatus, DocType
from app.services.document_service import DocumentService

# =====================================================================
# Helpers
# =====================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_DOC_ID = uuid.UUID("aaaa1111-1111-1111-1111-111111111111")
_DOC_ID_2 = uuid.UUID("aaaa2222-2222-2222-2222-222222222222")


def _make_doc_obj(**overrides: Any) -> MagicMock:
    """Build a mock that quacks like a Document ORM instance."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _DOC_ID)
    obj.company_id = overrides.get("company_id", _COMPANY_ID)
    obj.doc_type = overrides.get("doc_type", DocType.TEN_K)
    obj.fiscal_year = overrides.get("fiscal_year", 2023)
    obj.fiscal_quarter = overrides.get("fiscal_quarter")
    obj.filing_date = overrides.get("filing_date", date(2024, 2, 15))
    obj.period_end_date = overrides.get("period_end_date", date(2023, 12, 31))
    obj.sec_accession = overrides.get("sec_accession")
    obj.source_url = overrides.get("source_url")
    obj.storage_key = overrides.get("storage_key", "11111111/10-K/2023/filing.pdf")
    obj.file_size_bytes = overrides.get("file_size_bytes", 1024)
    obj.page_count = overrides.get("page_count", 10)
    obj.status = overrides.get("status", DocStatus.UPLOADED)
    obj.error_message = overrides.get("error_message")
    obj.processing_started_at = overrides.get("processing_started_at")
    obj.processing_completed_at = overrides.get("processing_completed_at")
    obj.created_at = overrides.get("created_at", _NOW)
    obj.updated_at = overrides.get("updated_at", _NOW)
    obj.sections = overrides.get("sections", [])
    return obj


def _make_company_obj(**overrides: Any) -> MagicMock:
    """Build a mock Company ORM instance."""
    obj = MagicMock(spec=[])
    obj.id = overrides.get("id", _COMPANY_ID)
    obj.ticker = overrides.get("ticker", "AAPL")
    obj.name = overrides.get("name", "Apple Inc.")
    obj.cik = overrides.get("cik", "0000320193")
    return obj


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture()
def mock_doc_service() -> AsyncMock:
    """Return an AsyncMock of DocumentService."""
    svc = AsyncMock(spec=DocumentService)
    # Give it a mock session for repo access
    svc._session = AsyncMock()
    return svc


@pytest.fixture()
def _override_doc_service(app, mock_doc_service):
    """Override the document service dependency."""
    from app.api.documents import _get_document_service

    app.dependency_overrides[_get_document_service] = lambda: mock_doc_service
    yield
    app.dependency_overrides.pop(_get_document_service, None)


# =====================================================================
# POST /api/v1/companies/{company_id}/documents (Upload)
# =====================================================================


class TestUploadDocument:
    """Tests for document upload endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, _override_doc_service):
        pass

    def test_upload_success(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        """Upload a valid PDF returns 202."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Test content")
        pdf_bytes = doc.tobytes()
        doc.close()

        mock_doc_service.upload_document.return_value = _make_doc_obj()

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_by_id.return_value = _make_company_obj()

        with patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_repo_instance), \
             patch("app.worker.tasks.ingestion_tasks.ingest_document") as mock_task:
            mock_task.delay = MagicMock()

            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents",
                headers=auth_header,
                files={"file": ("filing.pdf", pdf_bytes, "application/pdf")},
                data={
                    "doc_type": "10-K",
                    "fiscal_year": "2023",
                    "filing_date": "2024-02-15",
                    "period_end_date": "2023-12-31",
                },
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "document_id" in data
        assert data["status"] == "uploaded"

    def test_upload_unsupported_file_type(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        """Upload a JPEG file should return 422."""
        jpeg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_by_id.return_value = _make_company_obj()

        with patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_repo_instance):
            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents",
                headers=auth_header,
                files={"file": ("image.pdf", jpeg_data, "application/pdf")},
                data={
                    "doc_type": "10-K",
                    "fiscal_year": "2023",
                    "filing_date": "2024-02-15",
                    "period_end_date": "2023-12-31",
                },
            )

        assert resp.status_code == 422

    def test_upload_company_not_found(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        """Upload to non-existent company returns 404."""
        pdf_data = b"%PDF-1.4 fake pdf content"

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_by_id.return_value = None

        with patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_repo_instance):
            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents",
                headers=auth_header,
                files={"file": ("filing.pdf", pdf_data, "application/pdf")},
                data={
                    "doc_type": "10-K",
                    "fiscal_year": "2023",
                    "filing_date": "2024-02-15",
                    "period_end_date": "2023-12-31",
                },
            )

        assert resp.status_code == 404

    def test_upload_duplicate_returns_409(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        """Upload a duplicate document returns 409."""
        pdf_data = b"%PDF-1.4 fake pdf content"
        mock_doc_service.upload_document.side_effect = ConflictError(
            "Document already exists for 10-K 2023"
        )

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_by_id.return_value = _make_company_obj()

        with patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_repo_instance):
            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents",
                headers=auth_header,
                files={"file": ("filing.pdf", pdf_data, "application/pdf")},
                data={
                    "doc_type": "10-K",
                    "fiscal_year": "2023",
                    "filing_date": "2024-02-15",
                    "period_end_date": "2023-12-31",
                },
            )

        assert resp.status_code == 409

    def test_upload_invalid_fiscal_year(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        """Invalid fiscal_year returns 422."""
        pdf_data = b"%PDF-1.4 fake pdf content"

        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_by_id.return_value = _make_company_obj()

        with patch("app.db.repositories.company_repo.CompanyRepository", return_value=mock_repo_instance):
            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents",
                headers=auth_header,
                files={"file": ("filing.pdf", pdf_data, "application/pdf")},
                data={
                    "doc_type": "10-K",
                    "fiscal_year": "1800",
                    "filing_date": "2024-02-15",
                    "period_end_date": "2023-12-31",
                },
            )

        assert resp.status_code == 422


# =====================================================================
# GET /api/v1/companies/{company_id}/documents
# =====================================================================


class TestListDocuments:
    """Tests for document list endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, _override_doc_service):
        pass

    def test_list_empty(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.list_documents.return_value = ([], 0)

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents",
            headers=auth_header,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_documents(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        docs = [_make_doc_obj(), _make_doc_obj(id=_DOC_ID_2, fiscal_year=2022)]
        mock_doc_service.list_documents.return_value = (docs, 2)

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents",
            headers=auth_header,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_with_filters(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.list_documents.return_value = ([], 0)

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents",
            headers=auth_header,
            params={"doc_type": "10-K", "fiscal_year": 2023, "status": "ready"},
        )

        assert resp.status_code == 200
        # Verify service was called with filter params
        mock_doc_service.list_documents.assert_called_once()
        call_kwargs = mock_doc_service.list_documents.call_args
        assert call_kwargs.kwargs.get("doc_type") == "10-K" or call_kwargs[1].get("doc_type") == "10-K"


# =====================================================================
# GET /api/v1/companies/{company_id}/documents/{document_id}
# =====================================================================


class TestGetDocumentDetail:
    """Tests for document detail endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, _override_doc_service):
        pass

    def test_get_document_detail(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        doc = _make_doc_obj()
        mock_doc_service.get_document_detail.return_value = {
            "document": doc,
            "chunk_count": 42,
            "financial_data_extracted": True,
        }

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            headers=auth_header,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_count"] == 42
        assert data["financial_data_extracted"] is True

    def test_get_document_not_found(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.get_document_detail.side_effect = NotFoundError(
            entity="Document", entity_id=str(_DOC_ID),
        )

        resp = client.get(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            headers=auth_header,
        )

        assert resp.status_code == 404


# =====================================================================
# POST /api/v1/companies/{company_id}/documents/{document_id}/retry
# =====================================================================


class TestRetryDocument:
    """Tests for document retry endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, _override_doc_service):
        pass

    def test_retry_success(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.retry_document.return_value = _make_doc_obj()

        with patch("app.worker.tasks.ingestion_tasks.ingest_document") as mock_task:
            mock_task.delay = MagicMock()

            resp = client.post(
                f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}/retry",
                headers=auth_header,
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "uploaded"

    def test_retry_not_in_error_state(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.retry_document.side_effect = ValidationError(
            "Document is in 'ready' state, not 'error'."
        )

        resp = client.post(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}/retry",
            headers=auth_header,
        )

        assert resp.status_code == 422


# =====================================================================
# DELETE /api/v1/companies/{company_id}/documents/{document_id}
# =====================================================================


class TestDeleteDocument:
    """Tests for document delete endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self, _override_doc_service):
        pass

    def test_delete_success(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.delete_document.return_value = None

        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            headers=auth_header,
            params={"confirm": "true"},
        )

        assert resp.status_code == 204

    def test_delete_without_confirm(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            headers=auth_header,
        )

        assert resp.status_code == 422

    def test_delete_not_found(
        self, client: TestClient, auth_header: dict, mock_doc_service: AsyncMock,
    ) -> None:
        mock_doc_service.delete_document.side_effect = NotFoundError(
            entity="Document", entity_id=str(_DOC_ID),
        )

        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            headers=auth_header,
            params={"confirm": "true"},
        )

        assert resp.status_code == 404

    def test_requires_auth(self, client: TestClient) -> None:
        """Request without API key should return 401."""
        resp = client.delete(
            f"/api/v1/companies/{_COMPANY_ID}/documents/{_DOC_ID}",
            params={"confirm": "true"},
        )

        assert resp.status_code == 401
