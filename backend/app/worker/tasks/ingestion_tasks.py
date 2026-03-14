# filepath: backend/app/worker/tasks/ingestion_tasks.py
"""Ingestion pipeline Celery tasks.

Queue: ``ingestion``

Tasks:
  - ``ingest_document`` — Parse, chunk, embed, and index a single document
  - ``reprocess_document`` — Re-ingest a document that previously failed
"""

from __future__ import annotations

import asyncio

from app.observability.logging import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _try_extract_xbrl_financials(
    document_id: str,
    company_id: str,
    cik: str | None,
    fiscal_year: int | None,
    session: object,
) -> dict[str, object]:
    """Best-effort XBRL financial data extraction (T820).

    Attempts to extract structured financial data via the SEC XBRL API.
    Never raises — logs warnings and returns a result dict.

    Returns:
        Dict with keys: ``xbrl_attempted``, ``xbrl_periods_stored``, ``xbrl_warning``.
    """
    from app.services.financial_service import FinancialService
    import uuid as _uuid

    if not cik:
        logger.info(
            "Skipping XBRL extraction: company has no CIK",
            document_id=document_id,
            company_id=company_id,
        )
        return {
            "xbrl_attempted": False,
            "xbrl_periods_stored": 0,
            "xbrl_warning": "Company has no CIK — XBRL extraction skipped",
        }

    try:
        svc = FinancialService(session)  # type: ignore[arg-type]
        stored = await svc.extract_and_store_financials(
            company_id=_uuid.UUID(company_id),
            cik=cik,
            document_id=_uuid.UUID(document_id),
            start_year=fiscal_year,
            end_year=fiscal_year,
        )

        if stored == 0:
            logger.warning(
                "No XBRL financial data found for filing — text ingestion unaffected",
                document_id=document_id,
                company_id=company_id,
                cik=cik,
                fiscal_year=fiscal_year,
            )
            return {
                "xbrl_attempted": True,
                "xbrl_periods_stored": 0,
                "xbrl_warning": "No XBRL data available for this filing",
            }

        logger.info(
            "XBRL financial data extracted successfully",
            document_id=document_id,
            company_id=company_id,
            periods_stored=stored,
        )
        return {
            "xbrl_attempted": True,
            "xbrl_periods_stored": stored,
            "xbrl_warning": None,
        }

    except Exception as exc:
        logger.warning(
            "XBRL extraction failed — text ingestion unaffected",
            document_id=document_id,
            company_id=company_id,
            error=str(exc),
        )
        return {
            "xbrl_attempted": True,
            "xbrl_periods_stored": 0,
            "xbrl_warning": f"XBRL extraction failed: {exc}",
        }


async def _ingest_document_async(document_id: str) -> dict:
    """Async implementation of document ingestion.

    Transaction boundaries
    ~~~~~~~~~~~~~~~~~~~~~~
    This function manages its own DB session (not the FastAPI dependency).
    Three distinct transaction boundaries exist:

    1. **Happy path commit** (line ~142): After ``run_ingestion_pipeline``
       succeeds, the session is committed so the document moves to READY and
       all chunks/sections are persisted atomically.

    2. **XBRL commit** (line ~160): If XBRL extraction stores financial
       periods, a *second* commit persists that data.  This is deliberately
       separate so that XBRL failures never roll back the primary ingestion.

    3. **Error-path rollback + status update** (lines ~170, ~196): On
       ``IngestionError`` or unexpected ``Exception`` the main session is
       rolled back, and a *fresh* session is opened solely to mark the
       document as ERROR — isolating the error-status write from any dirty
       state in the original session.
    """
    from app.config import get_settings
    from app.db.repositories.company_repo import CompanyRepository
    from app.db.repositories.document_repo import DocumentRepository
    from app.db.session import get_session_factory
    from app.ingestion.pipeline import IngestionError, run_ingestion_pipeline
    from app.models.document import DocStatus

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        try:
            repo = DocumentRepository(session)
            doc = await repo.get_by_id(document_id)
            if doc is None:
                logger.error("Document not found for ingestion", document_id=document_id)
                return {"status": "error", "message": "Document not found"}

            result = await run_ingestion_pipeline(
                document=doc,
                session=session,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )

            # ── TX-1: Commit text ingestion (doc → READY, chunks, sections) ─
            await session.commit()

            # ── T820: Best-effort XBRL financial extraction ──────
            # Runs AFTER text ingestion succeeds. Failures here
            # are logged but never block the document from being READY.
            company_repo = CompanyRepository(session)
            company = await company_repo.get_by_id(doc.company_id)
            cik = company.cik if company else None

            xbrl_result = await _try_extract_xbrl_financials(
                document_id=document_id,
                company_id=str(doc.company_id),
                cik=cik,
                fiscal_year=doc.fiscal_year,
                session=session,
            )

            if xbrl_result.get("xbrl_periods_stored"):
                # ── TX-2: Commit XBRL financial data (separate from text) ──
                await session.commit()

            return {
                "status": "completed",
                "document_id": document_id,
                **result.to_dict(),
                **xbrl_result,
            }

        except IngestionError as exc:
            # ── TX-3a: Rollback dirty session on pipeline failure ────────
            await session.rollback()

            # Open a fresh session to mark the document as ERROR so the
            # status write is isolated from the failed transaction.
            async with factory() as err_session:
                err_repo = DocumentRepository(err_session)
                doc = await err_repo.get_by_id(document_id)
                if doc and doc.status != DocStatus.ERROR:
                    await err_repo.update_status(
                        doc, DocStatus.ERROR, error_message=str(exc),
                    )
                    await err_session.commit()

            logger.error(
                "Ingestion failed",
                document_id=document_id,
                stage=exc.stage,
                error=str(exc),
            )
            return {
                "status": "error",
                "document_id": document_id,
                "stage": exc.stage,
                "message": str(exc),
            }

        except Exception as exc:
            # ── TX-3b: Rollback on unexpected error ──────────────────────
            await session.rollback()

            # Fresh session for error-status write (same pattern as TX-3a).
            async with factory() as err_session:
                err_repo = DocumentRepository(err_session)
                doc = await err_repo.get_by_id(document_id)
                if doc and doc.status != DocStatus.ERROR:
                    await err_repo.update_status(
                        doc, DocStatus.ERROR,
                        error_message=f"Unexpected error: {exc}",
                    )
                    await err_session.commit()

            logger.error(
                "Ingestion failed unexpectedly",
                document_id=document_id,
                error=str(exc),
            )
            raise


@celery_app.task(
    name="app.worker.tasks.ingestion_tasks.ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="ingestion",
    acks_late=True,
)
def ingest_document(self, document_id: str) -> dict:
    """Parse, chunk, embed, and index a document.

    Args:
        document_id: UUID of the Document record to ingest.

    Returns:
        Dict with ingestion stats (chunks, sections, duration).
    """
    logger.info("Starting document ingestion", document_id=document_id, task_id=self.request.id)
    try:
        return _run_async(_ingest_document_async(document_id))
    except Exception as exc:
        logger.error(
            "Ingestion task error",
            document_id=document_id,
            error=str(exc),
            retry=self.request.retries,
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="app.worker.tasks.ingestion_tasks.reprocess_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="ingestion",
    acks_late=True,
)
def reprocess_document(self, document_id: str) -> dict:
    """Re-ingest a document that previously failed.

    Same as ingest_document — the document's status has already been
    reset to UPLOADED by the retry API endpoint.
    """
    logger.info("Re-processing document", document_id=document_id, task_id=self.request.id)
    try:
        return _run_async(_ingest_document_async(document_id))
    except Exception as exc:
        logger.error(
            "Reprocess task error",
            document_id=document_id,
            error=str(exc),
        )
        raise self.retry(exc=exc) from exc
