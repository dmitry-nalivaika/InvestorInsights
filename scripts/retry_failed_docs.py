#!/usr/bin/env python3
"""
Reset all documents in 'error' status back to 'uploaded' and
re-dispatch ingestion tasks via Celery.

Usage:
    cd /path/to/InvestorInsights
    source .venv/bin/activate
    python scripts/retry_failed_docs.py
"""

import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main() -> None:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "company_analysis")
    user = os.getenv("DB_USER", "analyst")
    password = os.getenv("DB_PASSWORD", "analyst_password")

    conn = psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Find error documents
    cur.execute(
        "SELECT id, doc_type, fiscal_year, status, error_message "
        "FROM documents WHERE status = 'error' ORDER BY created_at"
    )
    error_docs = cur.fetchall()

    if not error_docs:
        print("✅ No documents in 'error' status. Nothing to retry.")
        conn.close()
        return

    print(f"Found {len(error_docs)} document(s) in 'error' status:\n")
    for doc in error_docs:
        err_msg = (doc[4] or "")[:80]
        print(f"  {doc[0]}  {doc[1]} {doc[2]}  — {err_msg}")

    # Reset to 'uploaded'
    doc_ids = [doc[0] for doc in error_docs]
    cur.execute(
        "UPDATE documents SET status = 'uploaded', error_message = NULL, "
        "processing_started_at = NULL, processing_completed_at = NULL "
        "WHERE id = ANY(%s)",
        (doc_ids,),
    )
    print(f"\n✅ Reset {len(doc_ids)} document(s) to 'uploaded' status.")

    # Dispatch Celery tasks
    try:
        from app.worker.tasks.ingestion_tasks import ingest_document

        for doc_id in doc_ids:
            ingest_document.delay(str(doc_id))
        print(f"✅ Dispatched {len(doc_ids)} ingestion task(s) to Celery.")
    except Exception as exc:
        print(f"⚠️  Could not dispatch Celery tasks: {exc}")
        print("   You can dispatch manually or use the API retry endpoint.")

    conn.close()


if __name__ == "__main__":
    main()
