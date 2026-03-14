# filepath: backend/app/schemas/document.py
"""Pydantic schemas for Document endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.document import DocStatus, DocType  # noqa: TC001 - needed at runtime by Pydantic
from app.schemas.common import AppBaseModel, PaginatedResponse

# ── Request schemas ──────────────────────────────────────────────


class DocumentUpload(AppBaseModel):
    """Metadata accompanying a document file upload (multipart/form-data)."""

    doc_type: DocType
    fiscal_year: int = Field(..., ge=1990, le=2100)
    fiscal_quarter: int | None = Field(None, ge=1, le=4)
    filing_date: date
    period_end_date: date
    sec_accession: str | None = Field(None, max_length=30)
    source_url: str | None = Field(None, max_length=500)

    @field_validator("fiscal_quarter")
    @classmethod
    def quarter_required_for_10q(cls, v: int | None, info: Any) -> int | None:
        """10-Q filings must specify a quarter."""
        # info.data may not have doc_type yet if validation order differs;
        # the service layer enforces this as a business rule too.
        return v


class FetchSECRequest(AppBaseModel):
    """POST /api/v1/companies/{company_id}/documents/fetch-sec."""

    filing_types: list[str] = Field(
        default=["10-K", "10-Q"],
        description="Filing types to fetch",
    )
    years_back: int = Field(10, ge=1, le=30)


# ── Response schemas ─────────────────────────────────────────────


class DocumentRead(AppBaseModel):
    """Document object returned by list / detail endpoints."""

    id: uuid.UUID
    company_id: uuid.UUID
    doc_type: DocType
    fiscal_year: int
    fiscal_quarter: int | None = None
    filing_date: date
    period_end_date: date
    sec_accession: str | None = None
    source_url: str | None = None
    storage_key: str
    file_size_bytes: int | None = None
    page_count: int | None = None
    status: DocStatus
    error_message: str | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SectionSummary(AppBaseModel):
    """Lightweight section info embedded in document detail."""

    id: uuid.UUID
    section_key: str
    section_title: str | None = None
    char_count: int = 0
    token_count: int | None = None


class DocumentDetail(DocumentRead):
    """GET /api/v1/companies/{company_id}/documents/{document_id}."""

    sections: list[SectionSummary] = Field(default_factory=list)
    chunk_count: int = 0
    financial_data_extracted: bool = False


class DocumentList(PaginatedResponse[DocumentRead]):
    """Paginated list of documents."""

    pass


class DocumentUploadResponse(AppBaseModel):
    """202 Accepted response after document upload."""

    document_id: uuid.UUID
    status: str = "uploaded"
    message: str = "Document uploaded and queued for processing"


class FetchSECResponse(AppBaseModel):
    """202 Accepted response after SEC fetch request."""

    task_id: uuid.UUID
    message: str = "Fetching filings from SEC EDGAR"
    estimated_filings: int = 0


# Rebuild models to resolve forward references (required with
# ``from __future__ import annotations`` + Pydantic v2).
DocumentUpload.model_rebuild()
DocumentRead.model_rebuild()
DocumentDetail.model_rebuild()
