# filepath: backend/app/worker/tasks/sec_fetch_tasks.py
"""
SEC EDGAR fetch Celery tasks.

Queue: ``sec_fetch``

Tasks (implemented in later phases):
  - ``fetch_sec_filings`` — Fetch filings from SEC EDGAR for a company
"""

from __future__ import annotations

from app.worker.celery_app import celery_app


@celery_app.task(
    name="app.worker.tasks.sec_fetch_tasks.fetch_sec_filings",
    bind=True,
    max_retries=5,
    default_retry_delay=120,
    queue="sec_fetch",
    acks_late=True,
)
def fetch_sec_filings(
    self,
    company_id: str,
    filing_types: list,
    year_start: int,
    year_end: int,
) -> dict:
    """Fetch filings from SEC EDGAR for a company.

    Args:
        company_id: UUID of the Company.
        filing_types: List of filing types (e.g. ["10-K", "10-Q"]).
        year_start: Start year (inclusive).
        year_end: End year (inclusive).

    Returns:
        Dict with fetch results (documents created, errors).
    """
    raise NotImplementedError("fetch_sec_filings task not yet implemented")
