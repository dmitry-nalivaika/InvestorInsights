# filepath: backend/app/worker/tasks/ingestion_tasks.py
"""
Ingestion pipeline Celery tasks.

Queue: ``ingestion``

Tasks (implemented in later phases):
  - ``ingest_document`` — Parse, chunk, embed, and index a single document
  - ``reprocess_document`` — Re-ingest a document that previously failed
"""

from __future__ import annotations

from app.worker.celery_app import celery_app


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
    raise NotImplementedError("ingest_document task not yet implemented")


@celery_app.task(
    name="app.worker.tasks.ingestion_tasks.reprocess_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="ingestion",
    acks_late=True,
)
def reprocess_document(self, document_id: str) -> dict:
    """Re-ingest a document that previously failed."""
    raise NotImplementedError("reprocess_document task not yet implemented")
