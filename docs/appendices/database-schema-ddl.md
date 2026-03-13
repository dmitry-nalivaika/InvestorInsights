# Database Schema (DDL)

> Referenced from [System Specification — §7.2 Complete DDL](../system_specification.md#72-complete-ddl)

```sql
-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Enum Types
-- ============================================================
CREATE TYPE doc_type_enum AS ENUM ('10-K', '10-Q', '8-K', '20-F', 'DEF14A', 'OTHER');
CREATE TYPE doc_status_enum AS ENUM ('uploaded', 'parsing', 'parsed', 'embedding', 'ready', 'error');
CREATE TYPE criteria_category_enum AS ENUM (
    'profitability', 'valuation', 'growth', 'liquidity',
    'solvency', 'efficiency', 'dividend', 'quality', 'custom'
);
CREATE TYPE comparison_op_enum AS ENUM (
    '>', '>=', '<', '<=', '=', 'between', 'trend_up', 'trend_down'
);

-- ============================================================
-- Companies
-- ============================================================
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    cik             VARCHAR(20),
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    description     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_companies_ticker UNIQUE (ticker)
);

CREATE INDEX idx_companies_cik ON companies(cik) WHERE cik IS NOT NULL;

-- ============================================================
-- Documents
-- ============================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    doc_type        doc_type_enum NOT NULL,
    fiscal_year     INT NOT NULL,
    fiscal_quarter  INT,
    filing_date     DATE NOT NULL,
    period_end_date DATE NOT NULL,
    sec_accession   VARCHAR(30),
    source_url      VARCHAR(500),
    storage_bucket  VARCHAR(100) NOT NULL DEFAULT 'filings',
    storage_key     VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    page_count      INT,
    status          doc_status_enum NOT NULL DEFAULT 'uploaded',
    error_message   TEXT,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_documents_period UNIQUE (company_id, doc_type, fiscal_year, fiscal_quarter),
    CONSTRAINT chk_quarter_range CHECK (fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4),
    CONSTRAINT chk_fiscal_year CHECK (fiscal_year BETWEEN 1990 AND 2100)
);

CREATE INDEX idx_documents_company ON documents(company_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_company_year ON documents(company_id, fiscal_year);

-- ============================================================
-- Document Sections
-- ============================================================
CREATE TABLE document_sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_key     VARCHAR(50) NOT NULL,
    section_title   VARCHAR(255),
    content_text    TEXT NOT NULL,
    page_start      INT,
    page_end        INT,
    char_count      INT NOT NULL DEFAULT 0,
    token_count     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_section_per_doc UNIQUE (document_id, section_key)
);

CREATE INDEX idx_sections_document ON document_sections(document_id);

-- ============================================================
-- Document Chunks (for vector search metadata tracking)
-- ============================================================
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id      UUID REFERENCES document_sections(id) ON DELETE SET NULL,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    char_count      INT NOT NULL DEFAULT 0,
    token_count     INT,
    embedding_model VARCHAR(100),
    vector_id       VARCHAR(200),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_chunk_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_company ON document_chunks(company_id);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector_id ON document_chunks(vector_id) WHERE vector_id IS NOT NULL;

-- ============================================================
-- Financial Statements
-- ============================================================
CREATE TABLE financial_statements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    fiscal_year     INT NOT NULL,
    fiscal_quarter  INT,
    period_end_date DATE NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    statement_data  JSONB NOT NULL,
    source          VARCHAR(50) NOT NULL DEFAULT 'xbrl_api',
    raw_xbrl_data   JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_financial_period UNIQUE (company_id, fiscal_year, fiscal_quarter),
    CONSTRAINT chk_fin_quarter CHECK (fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4)
);

CREATE INDEX idx_financials_company ON financial_statements(company_id);
CREATE INDEX idx_financials_company_year ON financial_statements(company_id, fiscal_year);

-- ============================================================
-- Analysis Profiles
-- ============================================================
CREATE TABLE analysis_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    is_default      BOOLEAN NOT NULL DEFAULT false,
    version         INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_profile_name UNIQUE (name)
);

-- ============================================================
-- Analysis Criteria
-- ============================================================
CREATE TABLE analysis_criteria (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES analysis_profiles(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    category        criteria_category_enum NOT NULL,
    description     TEXT,
    formula         VARCHAR(500) NOT NULL,
    is_custom_formula BOOLEAN NOT NULL DEFAULT false,
    comparison      comparison_op_enum NOT NULL,
    threshold_value NUMERIC(20, 6),
    threshold_low   NUMERIC(20, 6),
    threshold_high  NUMERIC(20, 6),
    weight          NUMERIC(10, 4) NOT NULL DEFAULT 1.0,
    lookback_years  INT NOT NULL DEFAULT 5,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_weight_positive CHECK (weight > 0),
    CONSTRAINT chk_lookback_positive CHECK (lookback_years > 0 AND lookback_years <= 20),
    CONSTRAINT chk_threshold_between CHECK (
        comparison != 'between' OR (threshold_low IS NOT NULL AND threshold_high IS NOT NULL)
    ),
    CONSTRAINT chk_threshold_single CHECK (
        comparison IN ('between', 'trend_up', 'trend_down') OR threshold_value IS NOT NULL
    )
);

CREATE INDEX idx_criteria_profile ON analysis_criteria(profile_id);

-- ============================================================
-- Analysis Results
-- ============================================================
CREATE TABLE analysis_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    profile_id      UUID NOT NULL REFERENCES analysis_profiles(id) ON DELETE CASCADE,
    profile_version INT NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    overall_score   NUMERIC(10, 4) NOT NULL DEFAULT 0,
    max_score       NUMERIC(10, 4) NOT NULL DEFAULT 0,
    pct_score       NUMERIC(5, 2) NOT NULL DEFAULT 0,
    criteria_count  INT NOT NULL DEFAULT 0,
    passed_count    INT NOT NULL DEFAULT 0,
    failed_count    INT NOT NULL DEFAULT 0,
    result_details  JSONB NOT NULL DEFAULT '[]',
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_results_company ON analysis_results(company_id);
CREATE INDEX idx_results_profile ON analysis_results(profile_id);
CREATE INDEX idx_results_company_profile ON analysis_results(company_id, profile_id);
CREATE INDEX idx_results_run_at ON analysis_results(run_at DESC);

-- ============================================================
-- Chat Sessions
-- ============================================================
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    message_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_company ON chat_sessions(company_id);
CREATE INDEX idx_sessions_updated ON chat_sessions(updated_at DESC);

-- ============================================================
-- Chat Messages
-- ============================================================
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    sources         JSONB,
    token_count     INT,
    model_used      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);

-- ============================================================
-- Utility: updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_financials_updated_at BEFORE UPDATE ON financial_statements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON analysis_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```
