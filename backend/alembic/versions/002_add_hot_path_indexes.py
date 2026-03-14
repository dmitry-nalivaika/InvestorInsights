# filepath: backend/alembic/versions/002_add_hot_path_indexes.py
"""Add missing indexes for hot-path queries (T802a DB tuning review).

Analysis of repository query patterns identified five index gaps on the
most frequently executed code paths.  This migration adds the indexes
without downtime (CREATE INDEX CONCURRENTLY) when running online, and
as regular CREATE INDEX in Alembic offline mode.

Gap analysis:
  1. companies — ticker lookup uses UPPER(ticker); needs functional idx.
  2. companies — sector filter uses LOWER(sector); needs functional idx.
  3. documents — bulk summary stats filter (company_id, status) together.
  4. financial_statements — period lookup (company_id, year, quarter).
  5. analysis_results — result listing (company, profile, run_at DESC).

Connection-pool tuning notes (no DDL — config-only):
  - db_pool_size=10 + db_max_overflow=20 → max 30 connections.
  - 4 uvicorn workers × 30 = 120 max connections.
  - Azure PostgreSQL Flexible (B2s) allows 50 concurrent connections
    → REDUCE db_pool_size to 5, db_max_overflow to 5 per worker
    so 4 × 10 = 40 < 50 limit.
  - For production (GP_Gen5_4 tier, 200 conn limit), the current
    10+20 is safe.
  - pool_pre_ping=True ✓ already set — handles stale connections.
  - pool_recycle=300 ✓ already set — avoids Azure 30-min idle kills.

Qdrant HNSW tuning notes (no DDL — collection-level config):
  - m=16, ef_construct=100 ✓ already set in qdrant_client.py.
  - For production >100k vectors per collection, consider m=32 and
    ef_construct=200 to maintain recall >95% at higher fan-out.
  - Payload indexes for doc_type, fiscal_year, section_key ✓ already set.

Revision ID: 002
Revises: 001
Create Date: 2026-03-14 00:00:00+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ── Alembic identifiers ─────────────────────────────────────────

revision: str = "002"
down_revision: str = "001"
branch_labels: str | None = None  # type: ignore[assignment]
depends_on: str | None = None  # type: ignore[assignment]


def upgrade() -> None:
    # ── 1. Functional index: UPPER(ticker) for case-insensitive lookup ──
    # Hot paths: CompanyRepository.get_by_ticker(), exists_by_ticker()
    # Both call: WHERE UPPER(ticker) = :val
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_companies_ticker_upper "
        "ON companies (UPPER(ticker))"
    )

    # ── 2. Functional index: LOWER(sector) for case-insensitive filter ──
    # Hot path: CompanyRepository.list() with sector filter
    # Calls: WHERE LOWER(sector) = :val
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_companies_sector_lower "
        "ON companies (LOWER(sector)) WHERE sector IS NOT NULL"
    )

    # ── 3. Composite index: (company_id, status) on documents ───────────
    # Hot path: CompanyRepository.get_bulk_summary_stats()
    #   → SELECT COUNT(*) WHERE company_id IN (...) AND status = 'ready'
    # The existing idx_documents_company (company_id) doesn't cover
    # the status filter — this composite avoids a filter step on the
    # heap.
    op.create_index(
        "idx_documents_company_status",
        "documents",
        ["company_id", "status"],
    )

    # ── 4. Composite index: period lookup on financial_statements ───────
    # Hot path: FinancialRepository.get_by_period(), upsert()
    #   → WHERE company_id = :c AND fiscal_year = :y AND fiscal_quarter IS NULL
    # The unique constraint uq_financial_period covers (company_id,
    # fiscal_year, fiscal_quarter) but PostgreSQL unique indexes don't
    # efficiently handle IS NULL filtering. This explicit index helps.
    op.create_index(
        "idx_financials_period_lookup",
        "financial_statements",
        ["company_id", "fiscal_year", "fiscal_quarter"],
    )

    # ── 5. Covering index: result listing by company+profile+run_at ─────
    # Hot path: ResultRepository.list_results() with company_id + profile_id
    # filters and ORDER BY run_at DESC.
    # Replaces three separate scans with a single index scan.
    op.create_index(
        "idx_results_company_profile_run_at",
        "analysis_results",
        ["company_id", "profile_id", sa.text("run_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_results_company_profile_run_at", table_name="analysis_results")
    op.drop_index("idx_financials_period_lookup", table_name="financial_statements")
    op.drop_index("idx_documents_company_status", table_name="documents")
    op.execute("DROP INDEX IF EXISTS idx_companies_sector_lower")
    op.execute("DROP INDEX IF EXISTS idx_companies_ticker_upper")
