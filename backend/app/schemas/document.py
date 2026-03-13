# filepath: backend/app/schemas/document.py
"""Pydantic schemas for Document endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import Field, field_validator

from app.models.document import DocStatus, DocType
from app.schemas.common import AppBaseModel, PaginatedResponse


# ── Request schemas ──────────────────────────────────────────────


class DocumentUpload(AppBaseModel):
    """Metadata accompanying a document file upload (multipart/form-data)."""

    doc_type: DocType
    fiscal_year: int = Field(..., ge=1990, le=2100)
    fiscal_quarter: Optional[int] = Field(None, ge=1, le=4)
    filing_date: date
    period_end_date: date
    sec_accession: Optional[str] = Field(None, max_length=30)
    source_url: Optional[str] = Field(None, max_length=500)

    @field_validator("fiscal_quarter")
    @classmethod
    def quarter_required_for_10q(cls, v: Optional[int], info: Any) -> Optional[int]:
        """10-Q filings must specify a quarter."""
        # info.data may not have doc_type yet if validation order differs;
        # the service layer enforces this as a business rule too.
        return v


class FetchSECRequest(AppBaseModel):
    """POST /api/v1/companies/{company_id}/documents/fetch-sec."""

    filing_types: List[str] = Field(
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
    fiscal_quarter: Optional[int] = None
    filing_date: date
    period_end_date: date
    sec_accession: Optional[str] = None
    source_url: Optional[str] = None
    storage_key: str
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None
    status: DocStatus
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SectionSummary(AppBaseModel):
    """Lightweight section info embedded in document detail."""

    id: uuid.UUID
    section_key: str
    section_title: Optional[str] = None
    char_count: int = 0
    token_count: Optional[int] = None


class DocumentDetail(DocumentRead):
    """GET /api/v1/companies/{company_id}/documents/{document_id}."""

    sections: List[SectionSummary] = Field(default_factory=list)
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
