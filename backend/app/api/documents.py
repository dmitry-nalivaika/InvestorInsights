# filepath: backend/app/api/documents.py
"""Document API routes.

Endpoints:
  POST   /api/v1/companies/{company_id}/documents              — Upload
  GET    /api/v1/companies/{company_id}/documents              — List
  GET    /api/v1/companies/{company_id}/documents/{document_id} — Detail
  POST   /api/v1/companies/{company_id}/documents/{document_id}/retry — Retry
  DELETE /api/v1/companies/{company_id}/documents/{document_id} — Delete
  POST   /api/v1/companies/{company_id}/documents/fetch-sec     — Auto-fetch
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.middleware.error_handler import NotFoundError, ValidationError
from app.api.pagination import PaginationQuery
from app.dependencies import DbSessionDep, StorageDep
from app.models.document import DocType
from app.observability.logging import get_logger
from app.schemas.document import (
    DocumentDetail,
    DocumentList,
    DocumentRead,
    DocumentUpload,
    DocumentUploadResponse,
    FetchSECRequest,
    FetchSECResponse,
    SectionSummary,
)
from app.services.document_service import DocumentService

logger = get_logger(__name__)

router = APIRouter(prefix="/companies/{company_id}/documents", tags=["documents"])

# Max upload size: 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Allowed MIME types (magic byte prefixes)
_ALLOWED_MAGIC: dict[bytes, str] = {
    b"%PDF": "application/pdf",
    b"<!DO": "text/html",    # <!DOCTYPE ...
    b"<htm": "text/html",    # <html ...
    b"<HTM": "text/html",
    b"<!do": "text/html",
}


# ── Helpers ──────────────────────────────────────────────────────


def _get_document_service(session: DbSessionDep, storage: StorageDep) -> DocumentService:
    """Build a request-scoped DocumentService."""
    return DocumentService(session, storage=storage)


DocumentServiceDep = Depends(_get_document_service)


def _validate_file_magic(data: bytes, filename: str) -> str:
    """Validate file by magic bytes. Returns detected content type.

    Raises:
        ValidationError: If file type is not supported.
    """
    if not data:
        raise ValidationError("Uploaded file is empty")

    prefix = data[:4]
    for magic, content_type in _ALLOWED_MAGIC.items():
        if prefix.startswith(magic):
            return content_type

    raise ValidationError(
        f"Unsupported file type for '{filename}'. Only PDF and HTML files are accepted.",
        details=[{"field": "file", "reason": "Invalid file format (magic bytes check failed)"}],
    )


def _parse_doc_type(value: str) -> DocType:
    """Parse doc_type string to DocType enum."""
    try:
        return DocType(value)
    except ValueError:
        valid = [t.value for t in DocType]
        raise ValidationError(
            f"Invalid doc_type '{value}'. Must be one of: {', '.join(valid)}"
        )


# ── POST /companies/{company_id}/documents ──────────────────────


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a filing document",
    description="Upload a PDF or HTML filing for processing.",
)
async def upload_document(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="PDF or HTML filing document"),
    doc_type: str = Form(..., description="Filing type: 10-K, 10-Q, 8-K, etc."),
    fiscal_year: int = Form(..., description="Fiscal year (1990-2100)"),
    fiscal_quarter: int | None = Form(None, description="Quarter (1-4, required for 10-Q)"),
    filing_date: str = Form(..., description="Filing date (YYYY-MM-DD)"),
    period_end_date: str = Form(..., description="Period end date (YYYY-MM-DD)"),
    sec_accession: str | None = Form(None, description="SEC accession number"),
    source_url: str | None = Form(None, description="Source URL"),
    service: DocumentService = DocumentServiceDep,
) -> DocumentUploadResponse:
    """Upload a document, validate, store, and queue for ingestion."""
    from datetime import date

    # Verify company exists
    from app.db.repositories.company_repo import CompanyRepository

    company_repo = CompanyRepository(service._session)
    company = await company_repo.get_by_id(company_id)
    if company is None:
        raise NotFoundError(entity="Company", entity_id=str(company_id))

    # Read and validate file
    file_data = await file.read()

    # T213 — File size enforcement
    if len(file_data) > _MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File too large: {len(file_data)} bytes. Maximum is 50 MB.",
            details=[{"field": "file", "reason": "File exceeds 50 MB limit"}],
        )

    # T213 — Magic byte validation
    _validate_file_magic(file_data, file.filename or "unknown")

    # Parse typed doc_type
    typed_doc_type = _parse_doc_type(doc_type)

    # Parse dates
    try:
        parsed_filing_date = date.fromisoformat(filing_date)
    except ValueError:
        raise ValidationError(
            f"Invalid filing_date format: '{filing_date}'. Expected YYYY-MM-DD."
        )
    try:
        parsed_period_end_date = date.fromisoformat(period_end_date)
    except ValueError:
        raise ValidationError(
            f"Invalid period_end_date format: '{period_end_date}'. Expected YYYY-MM-DD."
        )

    # Validate fiscal_year range
    if not (1990 <= fiscal_year <= 2100):
        raise ValidationError("fiscal_year must be between 1990 and 2100")

    # Validate quarter required for 10-Q
    if typed_doc_type == DocType.TEN_Q and fiscal_quarter is None:
        raise ValidationError("fiscal_quarter is required for 10-Q filings")

    if fiscal_quarter is not None and not (1 <= fiscal_quarter <= 4):
        raise ValidationError("fiscal_quarter must be between 1 and 4")

    # Build the schema object for the service
    payload = DocumentUpload(
        doc_type=typed_doc_type,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        filing_date=parsed_filing_date,
        period_end_date=parsed_period_end_date,
        sec_accession=sec_accession,
        source_url=source_url,
    )

    doc = await service.upload_document(
        company_id=company_id,
        payload=payload,
        file_data=file_data,
        filename=file.filename or f"filing.{doc_type.lower().replace('-', '')}",
    )

    # Dispatch Celery ingestion task (best-effort — FR-307)
    try:
        from app.worker.tasks.ingestion_tasks import ingest_document

        ingest_document.delay(str(doc.id))
        logger.info("Ingestion task dispatched", document_id=str(doc.id))
    except Exception as exc:
        logger.warning(
            "Failed to dispatch ingestion task — document saved for later retry",
            document_id=str(doc.id),
            error=str(exc),
        )

    return DocumentUploadResponse(
        document_id=doc.id,
        status="uploaded",
        message="Document uploaded and queued for processing",
    )


# ── GET /companies/{company_id}/documents ────────────────────────


@router.get(
    "",
    response_model=DocumentList,
    summary="List documents for a company",
)
async def list_documents(
    company_id: uuid.UUID,
    pagination: PaginationQuery = Depends(),
    doc_type: str | None = Query(None, description="Filter by document type"),
    fiscal_year: int | None = Query(None, description="Filter by fiscal year"),
    doc_status: str | None = Query(None, alias="status", description="Filter by status"),
    service: DocumentService = DocumentServiceDep,
) -> DocumentList:
    """Return a paginated list of documents for a company."""
    documents, total = await service.list_documents(
        company_id=company_id,
        doc_type=doc_type,
        fiscal_year=fiscal_year,
        status=doc_status,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    items = [DocumentRead.model_validate(d) for d in documents]
    return DocumentList(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


# ── GET /companies/{company_id}/documents/{document_id} ─────────


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Get document details with sections",
)
async def get_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentService = DocumentServiceDep,
) -> DocumentDetail:
    """Fetch document detail with sections, chunk count, financial flag."""
    detail = await service.get_document_detail(document_id, company_id)
    doc = detail["document"]
    sections = [
        SectionSummary(
            id=s.id,
            section_key=s.section_key,
            section_title=s.section_title,
            char_count=s.char_count,
            token_count=s.token_count,
        )
        for s in doc.sections
    ]
    doc_data = DocumentRead.model_validate(doc)
    return DocumentDetail(
        **doc_data.model_dump(),
        sections=sections,
        chunk_count=detail["chunk_count"],
        financial_data_extracted=detail["financial_data_extracted"],
    )


# ── POST /companies/{company_id}/documents/{document_id}/retry ──


@router.post(
    "/{document_id}/retry",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed document ingestion",
)
async def retry_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    service: DocumentService = DocumentServiceDep,
) -> DocumentUploadResponse:
    """Retry a failed document's ingestion pipeline."""
    doc = await service.retry_document(document_id, company_id)

    # Re-dispatch ingestion task
    try:
        from app.worker.tasks.ingestion_tasks import ingest_document

        ingest_document.delay(str(doc.id))
        logger.info("Retry ingestion task dispatched", document_id=str(doc.id))
    except Exception as exc:
        logger.warning(
            "Failed to dispatch retry ingestion task",
            document_id=str(doc.id),
            error=str(exc),
        )

    return DocumentUploadResponse(
        document_id=doc.id,
        status="uploaded",
        message="Document queued for re-processing",
    )


# ── DELETE /companies/{company_id}/documents/{document_id} ──────


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and all derived data",
)
async def delete_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    service: DocumentService = DocumentServiceDep,
) -> Response:
    """Delete a document with cascade cleanup (vectors, blob, DB)."""
    if not confirm:
        raise ValidationError(
            "Deletion requires confirm=true query parameter",
            details=[{"field": "confirm", "reason": "Must be true"}],
        )
    await service.delete_document(document_id, company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── POST /companies/{company_id}/documents/fetch-sec ─────────────


@router.post(
    "/fetch-sec",
    response_model=FetchSECResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Auto-fetch filings from SEC EDGAR",
)
async def fetch_sec_filings(
    company_id: uuid.UUID,
    payload: FetchSECRequest,
    service: DocumentService = DocumentServiceDep,
) -> FetchSECResponse:
    """Trigger an async SEC EDGAR filing fetch for the company."""
    from datetime import datetime

    # Verify company exists and has CIK
    from app.db.repositories.company_repo import CompanyRepository

    company_repo = CompanyRepository(service._session)
    company = await company_repo.get_by_id(company_id)
    if company is None:
        raise NotFoundError(entity="Company", entity_id=str(company_id))
    if not company.cik:
        raise ValidationError(
            f"Company '{company.ticker}' has no CIK. Cannot fetch from SEC EDGAR."
        )

    # Calculate year range
    current_year = datetime.now().year
    year_start = current_year - payload.years_back
    year_end = current_year

    # Dispatch Celery task
    task_id = uuid.uuid4()
    try:
        from app.worker.tasks.sec_fetch_tasks import fetch_sec_filings as fetch_task

        result = fetch_task.apply_async(
            args=[str(company_id), payload.filing_types, year_start, year_end],
            task_id=str(task_id),
        )
        task_id = uuid.UUID(result.id)
    except Exception as exc:
        logger.warning(
            "Failed to dispatch SEC fetch task",
            company_id=str(company_id),
            error=str(exc),
        )

    return FetchSECResponse(
        task_id=task_id,
        message="Fetching filings from SEC EDGAR",
        estimated_filings=payload.years_back * len(payload.filing_types),
    )
