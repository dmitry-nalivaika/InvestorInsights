# Data Model: InvestorInsights Platform

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Entity Relationship Diagram

```text
┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  companies   │     │    documents     │     │ document_sections │
│──────────────│     │──────────────────│     │───────────────────│
│ id (PK)      │◀───┤│ id (PK)         │◀───┤│ id (PK)          │
│ ticker       │  1:N│ company_id (FK)  │  1:N│ document_id (FK) │
│ name         │     │ doc_type         │     │ section_key      │
│ cik          │     │ fiscal_year      │     │ section_title    │
│ sector       │     │ fiscal_quarter   │     │ content_text     │
│ industry     │     │ filing_date      │     │ token_count      │
│ description  │     │ period_end_date  │     └───────┬───────────┘
│ created_at   │     │ sec_accession    │             │
│ updated_at   │     │ source_url       │             │ 1:N
└──────┬───────┘     │ storage_key      │             ▼
       │             │ status           │     ┌───────────────────┐
       │             │ error_message    │     │ document_chunks   │
       │             │ file_size_bytes  │     │───────────────────│
       │             │ page_count       │     │ id (PK)          │
       │             │ created_at       │     │ section_id (FK)  │
       │             │ updated_at       │     │ document_id (FK) │
       │             └──────┬───────────┘     │ company_id (FK) ←── companies.id (denormalised)
       │                    │                 │ chunk_index      │
       │                    │ 1:N             │ content          │
       │                    ▼                 │ token_count      │
       │           ┌──────────────────┐       │ embedding_model  │
       │           │financial_stmts   │       │ vector_id        │
       │           │──────────────────│       │ metadata (JSONB) │
       │           │ id (PK)         │       │ created_at       │
       ├──────────▶│ company_id (FK) │       └──────────────────┘
       │     1:N   │ document_id(FK) │
       │           │ fiscal_year     │
       │           │ fiscal_quarter  │
       │           │ period_end_date │
       │           │ statement_data  │
       │           │   (JSONB)       │
       │           └─────────────────┘
       │
       │           ┌──────────────────┐       ┌───────────────────┐
       │           │  chat_sessions   │       │  chat_messages    │
       │           │──────────────────│       │───────────────────│
       ├──────────▶│ id (PK)         │◀─────┤│ id (PK)          │
       │     1:N   │ company_id (FK) │   1:N │ session_id (FK)  │
       │           │ title           │       │ role             │
       │           │ created_at      │       │ content          │
       │           │ updated_at      │       │ sources (JSONB)  │
       │           └─────────────────┘       │ token_count      │
       │                                      │ created_at       │
       │                                      └──────────────────┘
       │
       │           ┌──────────────────┐       ┌───────────────────┐
       │           │analysis_profiles │       │analysis_criteria  │
       │           │──────────────────│       │───────────────────│
       │           │ id (PK)         │◀─────┤│ id (PK)          │
       │           │ name            │   1:N │ profile_id (FK)  │
       │           │ description     │       │ name             │
       │           │ is_default      │       │ category         │
       │           │ version         │       │ description      │
       │           │ created_at      │       │ formula          │
       │           │ updated_at      │       │ is_custom_formula│
       │           └──────┬──────────┘       │ comparison       │
       │                  │                  │ threshold_value  │
       │                  │                  │ threshold_low    │
       │                  │                  │ threshold_high   │
       │                  │                  │ weight           │
       │                  │                  │ lookback_years   │
       │                  │                  │ enabled          │
       │                  │                  │ sort_order       │
       │                  │                  └──────────────────┘
       │                  │
       │           ┌──────┴───────────┐
       │           │analysis_results  │
       │           │──────────────────│
       ├──────────▶│ id (PK)         │
             1:N   │ company_id (FK) │
                   │ profile_id (FK) │
                   │ profile_version │
                   │ run_at          │
                   │ overall_score   │
                   │ max_score       │
                   │ pct_score       │
                   │ criteria_count  │
                   │ passed_count    │
                   │ failed_count    │
                   │ result_details  │
                   │   (JSONB)       │
                   │ summary         │
                   └─────────────────┘
```

---

## Complete DDL

> The full PostgreSQL DDL (extensions, enums, all tables, indexes, constraints, triggers)
> is in [reference/database-schema-ddl.md](./reference/database-schema-ddl.md).

### Enum Types

```sql
CREATE TYPE doc_type_enum AS ENUM ('10-K', '10-Q', '8-K', '20-F', 'DEF14A', 'OTHER');
CREATE TYPE doc_status_enum AS ENUM ('uploaded', 'parsing', 'parsed', 'embedding', 'ready', 'error');
CREATE TYPE criteria_category_enum AS ENUM (
    'profitability', 'valuation', 'growth', 'liquidity',
    'solvency', 'efficiency', 'dividend', 'quality', 'custom'
);
CREATE TYPE comparison_op_enum AS ENUM (
    '>', '>=', '<', '<=', '=', 'between', 'trend_up', 'trend_down'
);
```

### Key Constraints

- `companies.ticker` — UNIQUE
- `documents (company_id, doc_type, fiscal_year, fiscal_quarter)` — UNIQUE (prevents duplicate periods)
- `document_sections (document_id, section_key)` — UNIQUE
- `document_chunks (document_id, chunk_index)` — UNIQUE
- `financial_statements (company_id, fiscal_year, fiscal_quarter)` — UNIQUE
- `analysis_profiles.name` — UNIQUE
- All FKs use `ON DELETE CASCADE` to the parent entity (company deletion cascades to everything)

---

## Financial Statement Data Schema (JSONB)

The `statement_data` column in `financial_statements` stores structured financial data:

```json
{
  "income_statement": {
    "revenue": 394328000000,
    "cost_of_revenue": 223546000000,
    "gross_profit": 170782000000,
    "research_and_development": 29915000000,
    "selling_general_admin": 24932000000,
    "operating_expenses": 54847000000,
    "operating_income": 115935000000,
    "interest_expense": 3933000000,
    "interest_income": 3999000000,
    "other_income_expense": 66000000,
    "income_before_tax": 116001000000,
    "income_tax_expense": 19006000000,
    "net_income": 96995000000,
    "eps_basic": 6.16,
    "eps_diluted": 6.13,
    "shares_outstanding_basic": 15744231000,
    "shares_outstanding_diluted": 15812547000,
    "ebitda": null,
    "depreciation_amortization": 11519000000
  },
  "balance_sheet": {
    "cash_and_equivalents": 29965000000,
    "short_term_investments": 35228000000,
    "accounts_receivable": 60932000000,
    "inventory": 6331000000,
    "total_current_assets": 143566000000,
    "property_plant_equipment": 43715000000,
    "goodwill": 0,
    "intangible_assets": 0,
    "long_term_investments": 100544000000,
    "total_assets": 352583000000,
    "accounts_payable": 62611000000,
    "short_term_debt": 15807000000,
    "total_current_liabilities": 153982000000,
    "long_term_debt": 98959000000,
    "total_liabilities": 290437000000,
    "common_stock": 73812000000,
    "retained_earnings": -214000000,
    "treasury_stock": 0,
    "total_equity": 62146000000,
    "book_value_per_share": null
  },
  "cash_flow": {
    "operating_cash_flow": 110543000000,
    "depreciation_in_cfo": 11519000000,
    "stock_based_compensation": 10833000000,
    "capital_expenditure": -10959000000,
    "acquisitions": 0,
    "investment_purchases": -29513000000,
    "investment_sales": 29917000000,
    "investing_cash_flow": -7077000000,
    "debt_issued": 0,
    "debt_repaid": -11151000000,
    "dividends_paid": -14841000000,
    "share_buybacks": -77550000000,
    "financing_cash_flow": -103362000000,
    "free_cash_flow": 99584000000,
    "net_change_in_cash": 104000000
  }
}
```

---

## Vector Store Schema (Qdrant)

```yaml
# One collection per company: company_{company_id}
collection_config:
  vectors:
    size: 3072           # text-embedding-3-large dimensions
    distance: Cosine
  hnsw_config:
    m: 16
    ef_construct: 100
  optimizers_config:
    indexing_threshold: 20000
  on_disk_payload: true

# Point payload schema:
point_payload:
  text: string              # Original chunk text
  company_id: string        # UUID
  document_id: string       # UUID
  doc_type: string          # "10-K", "10-Q"
  fiscal_year: integer
  fiscal_quarter: integer   # nullable
  section_key: string       # "item_1a", "item_7", etc.
  section_title: string     # "Risk Factors", "MD&A", etc.
  filing_date: string       # ISO date
  period_end_date: string   # ISO date
  chunk_index: integer
  token_count: integer

# Payload indexes (for filtered search):
payload_indexes:
  - field: doc_type
    type: keyword
  - field: fiscal_year
    type: integer
  - field: section_key
    type: keyword
```
