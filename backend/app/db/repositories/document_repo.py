# filepath: backend/app/db/repositories/document_repo.py
"""Document data access layer.

Provides async CRUD operations and query helpers for the Document model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.document import DocStatus, DocType, Document
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DocumentRepository:
    """Async repository for Document CRUD and queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Create ───────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> Document:
        """Insert a new document and flush to get the generated id."""
        doc = Document(**kwargs)
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        logger.info(
            "Document created",
            document_id=str(doc.id),
            doc_type=doc.doc_type.value,
            fiscal_year=doc.fiscal_year,
        )
        return doc

    # ── Read ─────────────────────────────────────────────────────

    async def get_by_id(
        self,
        document_id: uuid.UUID,
        *,
        with_sections: bool = False,
    ) -> Document | None:
        """Fetch a document by primary key, optionally eager-loading sections."""
        from sqlalchemy.orm import selectinload as _selectinload

        stmt = select(Document).where(Document.id == document_id)
        if with_sections:
            stmt = stmt.options(_selectinload(Document.sections))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_company_and_period(
        self,
        company_id: uuid.UUID,
        doc_type: DocType,
        fiscal_year: int,
        fiscal_quarter: int | None,
    ) -> Document | None:
        """Check for an existing document for the same period (duplicate check)."""
        stmt = select(Document).where(
            Document.company_id == company_id,
            Document.doc_type == doc_type,
            Document.fiscal_year == fiscal_year,
        )
        if fiscal_quarter is not None:
            stmt = stmt.where(Document.fiscal_quarter == fiscal_quarter)
        else:
            stmt = stmt.where(Document.fiscal_quarter.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_company(
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
        """Return a paginated list of documents for a company with optional filters."""
        base_stmt = select(Document).where(Document.company_id == company_id)
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.company_id == company_id)
        )

        # Apply filters
        if doc_type:
            base_stmt = base_stmt.where(Document.doc_type == doc_type)
            count_stmt = count_stmt.where(Document.doc_type == doc_type)
        if fiscal_year is not None:
            base_stmt = base_stmt.where(Document.fiscal_year == fiscal_year)
            count_stmt = count_stmt.where(Document.fiscal_year == fiscal_year)
        if status:
            base_stmt = base_stmt.where(Document.status == status)
            count_stmt = count_stmt.where(Document.status == status)

        # Count
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Sort
        sort_column = self._resolve_sort_column(sort_by)
        if sort_order.lower() == "desc":
            base_stmt = base_stmt.order_by(sort_column.desc())
        else:
            base_stmt = base_stmt.order_by(sort_column.asc())

        # Paginate
        base_stmt = base_stmt.limit(limit).offset(offset)

        result = await self._session.execute(base_stmt)
        documents = list(result.scalars().all())
        return documents, total

    async def count_by_company(self, company_id: uuid.UUID) -> int:
        """Return the total number of documents for a company."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.company_id == company_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_chunks(self, document_id: uuid.UUID) -> int:
        """Return the number of chunks for a document."""
        from app.models.chunk import DocumentChunk

        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def has_financial_data(self, document_id: uuid.UUID) -> bool:
        """Check if a document has associated financial data."""
        from app.models.financial import FinancialStatement

        stmt = (
            select(func.count())
            .select_from(FinancialStatement)
            .where(FinancialStatement.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    # ── Update ───────────────────────────────────────────────────

    async def update_status(
        self,
        document: Document,
        new_status: DocStatus,
        *,
        error_message: str | None = None,
    ) -> Document:
        """Transition a document to a new processing status."""
        from datetime import datetime, timezone

        old_status = document.status
        document.status = new_status
        document.error_message = error_message

        if new_status == DocStatus.PARSING and document.processing_started_at is None:
            document.processing_started_at = datetime.now(timezone.utc)
        if new_status in (DocStatus.READY, DocStatus.ERROR):
            document.processing_completed_at = datetime.now(timezone.utc)

        await self._session.flush()
        await self._session.refresh(document)

        logger.info(
            "Document status updated",
            document_id=str(document.id),
            old_status=old_status.value,
            new_status=new_status.value,
        )
        return document

    async def update(self, document: Document, **kwargs: Any) -> Document:
        """Apply partial updates to a document."""
        for key, value in kwargs.items():
            if hasattr(document, key):
                setattr(document, key, value)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    # ── Delete ───────────────────────────────────────────────────

    async def delete(self, document: Document) -> None:
        """Delete a document (cascade handled by ORM relationships)."""
        doc_id = str(document.id)
        await self._session.delete(document)
        await self._session.flush()
        logger.info("Document deleted", document_id=doc_id)

    # ── Bulk helpers ─────────────────────────────────────────────

    async def bulk_create_sections(self, sections: list[Any]) -> None:
        """Bulk insert document sections."""
        self._session.add_all(sections)
        await self._session.flush()

    async def bulk_create_chunks(self, chunks: list[Any]) -> None:
        """Bulk insert document chunks."""
        self._session.add_all(chunks)
        await self._session.flush()

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _resolve_sort_column(sort_by: str) -> Any:
        """Map sort_by string to a SQLAlchemy column."""
        mapping = {
            "fiscal_year": Document.fiscal_year,
            "filing_date": Document.filing_date,
            "created_at": Document.created_at,
            "status": Document.status,
            "doc_type": Document.doc_type,
        }
        return mapping.get(sort_by, Document.fiscal_year)
