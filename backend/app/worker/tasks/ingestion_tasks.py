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


async def _ingest_document_async(document_id: str) -> dict:
    """Async implementation of document ingestion."""
    from app.config import get_settings
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

            await session.commit()

            return {
                "status": "completed",
                "document_id": document_id,
                **result.to_dict(),
            }

        except IngestionError as exc:
            await session.rollback()

            # Mark document as error
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
            await session.rollback()

            # Mark document as error
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
