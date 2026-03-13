"""Initial schema — enums, 10 tables, indexes, constraints, triggers.

Mirrors the canonical DDL in reference/database-schema-ddl.md.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

# ── Alembic identifiers ─────────────────────────────────────────

revision: str = "001"
down_revision: str | None = None  # type: ignore[assignment]
branch_labels: str | None = None  # type: ignore[assignment]
depends_on: str | None = None  # type: ignore[assignment]

# ── Enum names (used in both upgrade and downgrade) ──────────────

DOC_TYPE_ENUM = "doc_type_enum"
DOC_STATUS_ENUM = "doc_status_enum"
CRITERIA_CATEGORY_ENUM = "criteria_category_enum"
COMPARISON_OP_ENUM = "comparison_op_enum"


def upgrade() -> None:
    # ── Extensions ───────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── Enum Types ───────────────────────────────────────────────
    # Use raw SQL to avoid duplicate CREATE TYPE in offline mode.
    op.execute("CREATE TYPE doc_type_enum AS ENUM ('10-K', '10-Q', '8-K', '20-F', 'DEF14A', 'OTHER')")
    op.execute("CREATE TYPE doc_status_enum AS ENUM ('uploaded', 'parsing', 'parsed', 'embedding', 'ready', 'error')")
    op.execute(
        "CREATE TYPE criteria_category_enum AS ENUM ("
        "'profitability', 'valuation', 'growth', 'liquidity', "
        "'solvency', 'efficiency', 'dividend', 'quality', 'custom')"
    )
    op.execute(
        "CREATE TYPE comparison_op_enum AS ENUM ("
        "'>', '>=', '<', '<=', '=', 'between', 'trend_up', 'trend_down')"
    )

    # ── Companies ────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cik", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("ticker", name="uq_companies_ticker"),
    )
    op.create_index("idx_companies_cik", "companies", ["cik"], postgresql_where=sa.text("cik IS NOT NULL"))

    # ── Documents ────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", ENUM("10-K", "10-Q", "8-K", "20-F", "DEF14A", "OTHER", name=DOC_TYPE_ENUM, create_type=False), nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("fiscal_quarter", sa.Integer, nullable=True),
        sa.Column("filing_date", sa.Date, nullable=False),
        sa.Column("period_end_date", sa.Date, nullable=False),
        sa.Column("sec_accession", sa.String(30), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("storage_bucket", sa.String(100), nullable=False, server_default="filings"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("status", ENUM("uploaded", "parsing", "parsed", "embedding", "ready", "error", name=DOC_STATUS_ENUM, create_type=False), nullable=False, server_default="uploaded"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "doc_type", "fiscal_year", "fiscal_quarter", name="uq_documents_period"),
        sa.CheckConstraint("fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4", name="chk_quarter_range"),
        sa.CheckConstraint("fiscal_year BETWEEN 1990 AND 2100", name="chk_fiscal_year"),
    )
    op.create_index("idx_documents_company", "documents", ["company_id"])
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_company_year", "documents", ["company_id", "fiscal_year"])

    # ── Document Sections ────────────────────────────────────────
    op.create_table(
        "document_sections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.String(50), nullable=False),
        sa.Column("section_title", sa.String(255), nullable=True),
        sa.Column("content_text", sa.Text, nullable=False),
        sa.Column("page_start", sa.Integer, nullable=True),
        sa.Column("page_end", sa.Integer, nullable=True),
        sa.Column("char_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "section_key", name="uq_section_per_doc"),
    )
    op.create_index("idx_sections_document", "document_sections", ["document_id"])

    # ── Document Chunks ──────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", UUID(as_uuid=True), sa.ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("vector_id", sa.String(200), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index"),
    )
    op.create_index("idx_chunks_company", "document_chunks", ["company_id"])
    op.create_index("idx_chunks_document", "document_chunks", ["document_id"])
    op.create_index("idx_chunks_vector_id", "document_chunks", ["vector_id"], postgresql_where=sa.text("vector_id IS NOT NULL"))

    # ── Financial Statements ─────────────────────────────────────
    op.create_table(
        "financial_statements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("fiscal_quarter", sa.Integer, nullable=True),
        sa.Column("period_end_date", sa.Date, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("statement_data", JSONB, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="xbrl_api"),
        sa.Column("raw_xbrl_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "fiscal_year", "fiscal_quarter", name="uq_financial_period"),
        sa.CheckConstraint("fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4", name="chk_fin_quarter"),
    )
    op.create_index("idx_financials_company", "financial_statements", ["company_id"])
    op.create_index("idx_financials_company_year", "financial_statements", ["company_id", "fiscal_year"])

    # ── Analysis Profiles ────────────────────────────────────────
    op.create_table(
        "analysis_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_profile_name"),
    )

    # ── Analysis Criteria ────────────────────────────────────────
    op.create_table(
        "analysis_criteria",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("analysis_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", ENUM(
            "profitability", "valuation", "growth", "liquidity",
            "solvency", "efficiency", "dividend", "quality", "custom",
            name=CRITERIA_CATEGORY_ENUM, create_type=False,
        ), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("formula", sa.String(500), nullable=False),
        sa.Column("is_custom_formula", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("comparison", ENUM(
            ">", ">=", "<", "<=", "=", "between", "trend_up", "trend_down",
            name=COMPARISON_OP_ENUM, create_type=False,
        ), nullable=False),
        sa.Column("threshold_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("threshold_low", sa.Numeric(20, 6), nullable=True),
        sa.Column("threshold_high", sa.Numeric(20, 6), nullable=True),
        sa.Column("weight", sa.Numeric(10, 4), nullable=False, server_default=sa.text("1.0")),
        sa.Column("lookback_years", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("weight > 0", name="chk_weight_positive"),
        sa.CheckConstraint("lookback_years > 0 AND lookback_years <= 20", name="chk_lookback_positive"),
        sa.CheckConstraint(
            "comparison != 'between' OR (threshold_low IS NOT NULL AND threshold_high IS NOT NULL)",
            name="chk_threshold_between",
        ),
        sa.CheckConstraint(
            "comparison IN ('between', 'trend_up', 'trend_down') OR threshold_value IS NOT NULL",
            name="chk_threshold_single",
        ),
    )
    op.create_index("idx_criteria_profile", "analysis_criteria", ["profile_id"])

    # ── Analysis Results ─────────────────────────────────────────
    op.create_table(
        "analysis_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("analysis_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_version", sa.Integer, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("overall_score", sa.Numeric(10, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("max_score", sa.Numeric(10, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("pct_score", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("criteria_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("passed_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("result_details", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_results_company", "analysis_results", ["company_id"])
    op.create_index("idx_results_profile", "analysis_results", ["profile_id"])
    op.create_index("idx_results_company_profile", "analysis_results", ["company_id", "profile_id"])
    op.create_index("idx_results_run_at", "analysis_results", ["run_at"], postgresql_using="btree", postgresql_ops={"run_at": "DESC"})

    # ── Chat Sessions ────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("message_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_sessions_company", "chat_sessions", ["company_id"])
    op.create_index("idx_sessions_updated", "chat_sessions", ["updated_at"], postgresql_using="btree", postgresql_ops={"updated_at": "DESC"})

    # ── Chat Messages ────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="chk_role"),
    )
    op.create_index("idx_messages_session", "chat_messages", ["session_id", "created_at"])

    # ── updated_at trigger function ──────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ── Attach triggers to tables with updated_at ────────────────
    for table in ("companies", "documents", "financial_statements", "analysis_profiles", "chat_sessions"):
        trigger_name = f"update_{table}_updated_at"
        op.execute(f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    # ── Drop triggers ────────────────────────────────────────────
    for table in ("chat_sessions", "analysis_profiles", "financial_statements", "documents", "companies"):
        trigger_name = f"update_{table}_updated_at"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # ── Drop tables (reverse dependency order) ───────────────────
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("analysis_results")
    op.drop_table("analysis_criteria")
    op.drop_table("analysis_profiles")
    op.drop_table("financial_statements")
    op.drop_table("document_chunks")
    op.drop_table("document_sections")
    op.drop_table("documents")
    op.drop_table("companies")

    # ── Drop enum types ──────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS comparison_op_enum")
    op.execute("DROP TYPE IF EXISTS criteria_category_enum")
    op.execute("DROP TYPE IF EXISTS doc_status_enum")
    op.execute("DROP TYPE IF EXISTS doc_type_enum")

    # ── Drop extensions ──────────────────────────────────────────
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
