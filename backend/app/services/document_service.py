# filepath: backend/app/services/document_service.py
"""Document business logic layer.

Orchestrates document CRUD operations, file storage in Azure Blob,
status state machine, duplicate detection, and cascade deletion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.middleware.error_handler import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.clients.qdrant_client import VectorStoreClient, get_qdrant_client
from app.clients.storage_client import StorageClient, get_storage_client
from app.db.repositories.document_repo import DocumentRepository
from app.models.document import DocStatus, Document
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.document import DocumentUpload

logger = get_logger(__name__)

# Valid status transitions (T202 — state machine)
_VALID_TRANSITIONS: dict[DocStatus, set[DocStatus]] = {
    DocStatus.UPLOADED: {DocStatus.PARSING, DocStatus.ERROR},
    DocStatus.PARSING: {DocStatus.PARSED, DocStatus.ERROR},
    DocStatus.PARSED: {DocStatus.EMBEDDING, DocStatus.ERROR},
    DocStatus.EMBEDDING: {DocStatus.READY, DocStatus.ERROR},
    DocStatus.READY: {DocStatus.PARSING},  # allow re-ingestion
    DocStatus.ERROR: {DocStatus.PARSING, DocStatus.UPLOADED},  # allow retry
}


class DocumentService:
    """Business logic for document management.

    Each instance is scoped to a single request/task.
    """

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageClient | None = None,
        vector_store: VectorStoreClient | None = None,
    ) -> None:
        self._repo = DocumentRepository(session)
        self._session = session
        self._storage: StorageClient | None = storage
        self._vector_store: VectorStoreClient | None = vector_store

    @property
    def storage(self) -> StorageClient:
        if self._storage is None:
            self._storage = get_storage_client()
        return self._storage

    @property
    def vector_store(self) -> VectorStoreClient:
        if self._vector_store is None:
            self._vector_store = get_qdrant_client()
        return self._vector_store

    # ── Upload ───────────────────────────────────────────────────

    async def upload_document(
        self,
        company_id: uuid.UUID,
        payload: DocumentUpload,
        file_data: bytes,
        filename: str,
    ) -> Document:
        """Upload a document: validate, store in blob, create DB record.

        Args:
            company_id: The owning company UUID.
            payload: Validated upload metadata.
            file_data: Raw file bytes.
            filename: Original filename.

        Returns:
            The created Document ORM instance with status=UPLOADED.

        Raises:
            ConflictError: Duplicate document for same period.
            ValidationError: Invalid file or metadata.
        """
        # T203 — Duplicate check
        existing = await self._repo.get_by_company_and_period(
            company_id=company_id,
            doc_type=payload.doc_type,
            fiscal_year=payload.fiscal_year,
            fiscal_quarter=payload.fiscal_quarter,
        )
        if existing:
            raise ConflictError(
                f"Document already exists for {payload.doc_type.value} "
                f"{payload.fiscal_year}"
                f"{'Q' + str(payload.fiscal_quarter) if payload.fiscal_quarter else ''}"
            )

        # Build storage key and upload to blob
        storage_key = StorageClient.build_storage_key(
            company_id=company_id,
            doc_type=payload.doc_type.value,
            fiscal_year=payload.fiscal_year,
            fiscal_quarter=payload.fiscal_quarter,
            filename=filename,
        )

        await self.storage.upload_blob(
            key=storage_key,
            data=file_data,
            overwrite=True,
        )

        # Create DB record
        doc = await self._repo.create(
            company_id=company_id,
            doc_type=payload.doc_type,
            fiscal_year=payload.fiscal_year,
            fiscal_quarter=payload.fiscal_quarter,
            filing_date=payload.filing_date,
            period_end_date=payload.period_end_date,
            sec_accession=payload.sec_accession,
            source_url=payload.source_url,
            storage_key=storage_key,
            file_size_bytes=len(file_data),
            status=DocStatus.UPLOADED,
        )

        logger.info(
            "Document uploaded",
            document_id=str(doc.id),
            company_id=str(company_id),
            doc_type=payload.doc_type.value,
            file_size=len(file_data),
        )
        return doc

    # ── Read ─────────────────────────────────────────────────────

    async def get_document(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        with_sections: bool = False,
    ) -> Document:
        """Fetch a single document, verifying it belongs to the company.

        Raises:
            NotFoundError: Document not found or doesn't belong to company.
        """
        doc = await self._repo.get_by_id(document_id, with_sections=with_sections)
        if doc is None or doc.company_id != company_id:
            raise NotFoundError(entity="Document", entity_id=str(document_id))
        return doc

    async def list_documents(
        self,
        company_id: uuid.UUID,
        *,
        doc_type: str | None = None,
        fiscal_year: int | None = None,
        status: str | None = None,
        sort_by: str = "fiscal_year",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        """Return a paginated, filtered list of documents for a company."""
        return await self._repo.list_by_company(
            company_id=company_id,
            doc_type=doc_type,
            fiscal_year=fiscal_year,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    async def get_document_detail(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return document with sections, chunk_count, financial_data_extracted."""
        doc = await self.get_document(
            document_id, company_id, with_sections=True,
        )
        chunk_count = await self._repo.count_chunks(document_id)
        has_financials = await self._repo.has_financial_data(document_id)
        return {
            "document": doc,
            "chunk_count": chunk_count,
            "financial_data_extracted": has_financials,
        }

    # ── Status state machine (T202) ──────────────────────────────

    async def transition_status(
        self,
        document: Document,
        new_status: DocStatus,
        *,
        error_message: str | None = None,
    ) -> Document:
        """Transition document to a new status, enforcing the state machine.

        Raises:
            ValidationError: Invalid status transition.
        """
        allowed = _VALID_TRANSITIONS.get(document.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from '{document.status.value}' to '{new_status.value}'"
            )
        return await self._repo.update_status(
            document, new_status, error_message=error_message,
        )

    # ── Retry (T214) ─────────────────────────────────────────────

    async def retry_document(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Document:
        """Retry a failed document ingestion.

        Resets the document to UPLOADED status for re-processing.

        Raises:
            NotFoundError: Document not found.
            ValidationError: Document not in error state.
        """
        doc = await self.get_document(document_id, company_id)
        if doc.status != DocStatus.ERROR:
            raise ValidationError(
                f"Document is in '{doc.status.value}' state, not 'error'. "
                "Only failed documents can be retried."
            )
        # Reset to allow re-ingestion from beginning
        doc = await self._repo.update_status(
            doc, DocStatus.UPLOADED, error_message=None,
        )
        logger.info(
            "Document marked for retry",
            document_id=str(document_id),
        )
        return doc

    # ── Delete with cascade (T215) ───────────────────────────────

    async def delete_document(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> None:
        """Delete a document and all derived data.

        Steps:
            1. Delete vectors from Qdrant
            2. Delete blob from storage
            3. Delete DB record (cascades sections, chunks, financials)

        Raises:
            NotFoundError: Document not found.
        """
        doc = await self.get_document(document_id, company_id)

        # 1. Delete vectors from Qdrant (best-effort)
        try:
            await self.vector_store.delete_vectors_by_document(
                company_id=company_id,
                document_id=document_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to delete vectors from Qdrant",
                document_id=str(document_id),
                error=str(exc),
            )

        # 2. Delete blob from storage (best-effort)
        try:
            await self.storage.delete_blob(doc.storage_key)
        except Exception as exc:
            logger.warning(
                "Failed to delete blob from storage",
                document_id=str(document_id),
                storage_key=doc.storage_key,
                error=str(exc),
            )

        # 3. Delete DB record (ORM cascade handles sections/chunks/financials)
        await self._repo.delete(doc)
        logger.info(
            "Document deleted",
            document_id=str(document_id),
            company_id=str(company_id),
        )
