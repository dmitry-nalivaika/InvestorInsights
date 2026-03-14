# filepath: backend/app/worker/tasks/sec_fetch_tasks.py
"""SEC EDGAR fetch Celery tasks.

Queue: ``sec_fetch``

Tasks:
  - ``fetch_sec_filings`` — Fetch filings from SEC EDGAR for a company
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


async def _fetch_sec_filings_async(
    company_id: str,
    filing_types: list,
    year_start: int,
    year_end: int,
) -> dict:
    """Async implementation of SEC filing fetch."""
    from app.clients.sec_client import get_sec_client
    from app.db.repositories.company_repo import CompanyRepository
    from app.db.repositories.document_repo import DocumentRepository
    from app.db.session import get_session_factory
    from app.models.document import DocStatus, DocType

    factory = get_session_factory()
    sec_client = get_sec_client()

    async with factory() as session:
        company_repo = CompanyRepository(session)
        doc_repo = DocumentRepository(session)

        company = await company_repo.get_by_id(company_id)
        if company is None:
            return {"status": "error", "message": "Company not found"}

        if not company.cik:
            return {"status": "error", "message": "Company has no CIK"}

        # Fetch filing index from SEC
        filings = await sec_client.get_filing_index(
            company.cik,
            filing_types=filing_types,
            start_year=year_start,
            end_year=year_end,
        )

        created = 0
        skipped = 0
        errors = 0

        for filing in filings:
            try:
                form = filing.get("form", "")
                filing_date_str = filing.get("filing_date", "")
                accession = filing.get("accession_number", "")
                primary_doc = filing.get("primary_document", "")

                if not filing_date_str or not accession:
                    skipped += 1
                    continue

                # Map form to DocType
                doc_type_map = {
                    "10-K": DocType.TEN_K,
                    "10-Q": DocType.TEN_Q,
                    "8-K": DocType.EIGHT_K,
                    "20-F": DocType.TWENTY_F,
                    "DEF 14A": DocType.DEF14A,
                }
                doc_type = doc_type_map.get(form, DocType.OTHER)

                # Parse fiscal year from filing date
                from datetime import date as date_type

                try:
                    filing_date = date_type.fromisoformat(filing_date_str)
                except ValueError:
                    skipped += 1
                    continue

                fiscal_year = filing_date.year
                fiscal_quarter = None
                if doc_type == DocType.TEN_Q:
                    fiscal_quarter = (filing_date.month - 1) // 3 + 1

                # Check for duplicate
                existing = await doc_repo.get_by_company_and_period(
                    company_id=company.id,
                    doc_type=doc_type,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                )
                if existing:
                    skipped += 1
                    continue

                # Download the filing document
                file_data = await sec_client.download_filing_document(
                    company.cik, accession, primary_doc,
                )

                # Store in blob
                from app.clients.storage_client import StorageClient, get_storage_client

                storage = get_storage_client()
                storage_key = StorageClient.build_storage_key(
                    company_id=company.id,
                    doc_type=doc_type.value,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    filename=primary_doc or f"{form.lower().replace(' ', '')}-{filing_date_str}",
                )
                await storage.upload_blob(key=storage_key, data=file_data, overwrite=True)

                # Create document record
                doc = await doc_repo.create(
                    company_id=company.id,
                    doc_type=doc_type,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    filing_date=filing_date,
                    period_end_date=filing_date,  # Approximate
                    sec_accession=accession,
                    source_url=filing.get("filing_url"),
                    storage_key=storage_key,
                    file_size_bytes=len(file_data),
                    status=DocStatus.UPLOADED,
                )

                # Dispatch ingestion task
                from app.worker.tasks.ingestion_tasks import ingest_document

                ingest_document.delay(str(doc.id))
                created += 1

            except Exception as exc:
                errors += 1
                logger.warning(
                    "Failed to fetch filing",
                    company_id=str(company.id),
                    filing=filing,
                    error=str(exc),
                )

        await session.commit()

        return {
            "status": "completed",
            "company_id": company_id,
            "filings_found": len(filings),
            "documents_created": created,
            "skipped": skipped,
            "errors": errors,
        }


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
    logger.info(
        "Starting SEC filing fetch",
        company_id=company_id,
        filing_types=filing_types,
        year_range=f"{year_start}-{year_end}",
        task_id=self.request.id,
    )
    try:
        return _run_async(
            _fetch_sec_filings_async(company_id, filing_types, year_start, year_end)
        )
    except Exception as exc:
        logger.error(
            "SEC fetch task error",
            company_id=company_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)
