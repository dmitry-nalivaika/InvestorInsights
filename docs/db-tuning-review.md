# filepath: docs/db-tuning-review.md
# Database Tuning Review — T802a

> Date: 2026-03-14 | Reviewer: Automated analysis of repository query patterns

## 1. Connection Pool Sizing

### Current Settings (config.py)

| Setting            | Old Default | New Default | Rationale                                       |
| ------------------ | ----------- | ----------- | ----------------------------------------------- |
| `db_pool_size`     | 10          | **5**       | Per-worker pool — fits Azure B2s (50 conn limit) |
| `db_max_overflow`  | 20          | **10**      | Burst headroom per worker                        |
| `pool_pre_ping`    | True        | True        | Detects stale conns after Azure idle timeout     |
| `pool_recycle`     | 300 s       | 300 s       | Avoids Azure 30-min idle kill                    |

### Budget Calculation

```
Total max connections = api_workers × (pool_size + max_overflow)

Development (1 worker):   1 × (5 + 10) = 15   (PostgreSQL default: 100)
Azure B2s   (2 workers):  2 × (5 + 10) = 30   (limit: 50 ✓)
Azure GP_Gen5_2 (4 wkr):  4 × (5 + 10) = 60   (limit: 100 ✓)
Azure GP_Gen5_4 (4 wkr):  4 × (5 + 10) = 60   (limit: 200 ✓)
```

**Celery workers** also open connections. With `worker_concurrency=4`
and 1 pool per worker process, budget an extra 4 × (5 + 10) = 60
connections for background tasks.

### Recommendations by Tier

| Azure Tier     | `db_pool_size` | `db_max_overflow` | `api_workers` | Max Conns |
| -------------- | -------------- | ----------------- | ------------- | --------- |
| B2s (dev)      | 5              | 5                 | 2             | 20        |
| GP_Gen5_2      | 5              | 10                | 4             | 60        |
| GP_Gen5_4      | 10             | 15                | 4             | 100       |

---

## 2. Query Index Audit

### Existing Indexes (001_initial_schema.py)

| Index                        | Table              | Columns                          | Type       |
| ---------------------------- | ------------------ | -------------------------------- | ---------- |
| PK (auto)                    | companies          | id                               | B-tree     |
| uq_companies_ticker          | companies          | ticker                           | Unique     |
| idx_companies_cik            | companies          | cik (WHERE NOT NULL)             | Partial    |
| idx_documents_company        | documents          | company_id                       | B-tree     |
| idx_documents_status         | documents          | status                           | B-tree     |
| idx_documents_company_year   | documents          | company_id, fiscal_year          | Composite  |
| idx_sections_document        | document_sections  | document_id                      | B-tree     |
| idx_chunks_company           | document_chunks    | company_id                       | B-tree     |
| idx_chunks_document          | document_chunks    | document_id                      | B-tree     |
| idx_chunks_vector_id         | document_chunks    | vector_id (WHERE NOT NULL)       | Partial    |
| idx_financials_company       | financial_stmts    | company_id                       | B-tree     |
| idx_financials_company_year  | financial_stmts    | company_id, fiscal_year          | Composite  |
| idx_criteria_profile         | analysis_criteria  | profile_id                       | B-tree     |
| idx_results_company          | analysis_results   | company_id                       | B-tree     |
| idx_results_profile          | analysis_results   | profile_id                       | B-tree     |
| idx_results_company_profile  | analysis_results   | company_id, profile_id           | Composite  |
| idx_results_run_at           | analysis_results   | run_at DESC                      | B-tree     |
| idx_sessions_company         | chat_sessions      | company_id                       | B-tree     |
| idx_sessions_updated         | chat_sessions      | updated_at DESC                  | B-tree     |
| idx_messages_session         | chat_messages      | session_id, created_at           | Composite  |

### Gaps Found → Added in 002_add_hot_path_indexes.py

| # | New Index                           | Table              | Columns / Expression             | Hot Path                                        |
|---|-------------------------------------|--------------------|----------------------------------|-------------------------------------------------|
| 1 | `idx_companies_ticker_upper`        | companies          | `UPPER(ticker)`                  | `get_by_ticker()`, `exists_by_ticker()`          |
| 2 | `idx_companies_sector_lower`        | companies          | `LOWER(sector)` WHERE NOT NULL   | `list()` with sector filter                      |
| 3 | `idx_documents_company_status`      | documents          | `company_id, status`             | `get_bulk_summary_stats()` ready-count query     |
| 4 | `idx_financials_period_lookup`      | financial_stmts    | `company_id, fiscal_year, fiscal_quarter` | `get_by_period()`, `upsert()`          |
| 5 | `idx_results_company_profile_run_at`| analysis_results   | `company_id, profile_id, run_at DESC` | `list_results()` with filters + sort       |

### Why Each Gap Matters

1. **Ticker lookup** — Used on every company-create (duplicate check) and
   SEC-fetch. Without the functional index, PostgreSQL must seq-scan and
   apply `UPPER()` to every row.

2. **Sector filter** — Dashboard companies list with sector dropdown.
   The functional index avoids a seq-scan + filter on the LOWER() expression.

3. **Document company+status** — The `get_bulk_summary_stats()` runs
   two GROUP BY queries on `company_id` with a status = 'ready' filter.
   The existing `idx_documents_company` can't push down the status
   predicate — this composite index gives an index-only scan.

4. **Financial period lookup** — The `get_by_period()` is called inside
   `upsert()` on every XBRL ingest. The unique constraint
   `uq_financial_period` covers (company_id, year, quarter) but
   PostgreSQL B-tree indexes with nullable columns (fiscal_quarter)
   benefit from an explicit covering index for the IS NULL pattern.

5. **Result listing** — The analysis results page sorts by `run_at DESC`
   with optional `company_id` + `profile_id` filters. The existing
   separate indexes require merge or hash joins. A triple-column index
   with trailing sort gives an index scan + backwards scan.

---

## 3. Qdrant HNSW Parameters

### Current Settings (qdrant_client.py → `ensure_collection`)

| Parameter        | Value | Notes                           |
| ---------------- | ----- | ------------------------------- |
| `m`              | 16    | Default — good for <100k vecs   |
| `ef_construct`   | 100   | Default — good recall at build  |
| `indexing_threshold` | 20000 | Segment merge threshold       |
| `on_disk_payload` | True | Keeps RAM for vectors only       |

### Payload Indexes

| Field          | Schema Type | Purpose                         |
| -------------- | ----------- | ------------------------------- |
| `doc_type`     | KEYWORD     | Filter by filing type            |
| `fiscal_year`  | INTEGER     | Filter by year range             |
| `section_key`  | KEYWORD     | Filter by SEC section (Item 1A) |

### Production Recommendations (>100k vectors/collection)

| Parameter        | Recommendation | Rationale                         |
| ---------------- | -------------- | --------------------------------- |
| `m`              | 32             | Higher fan-out → better recall    |
| `ef_construct`   | 200            | More candidates at build time     |
| `ef` (search)    | 128            | Tune per-query via search params  |
| `indexing_threshold` | 50000      | Larger segments → fewer merges    |

These can be set per-collection at creation or updated via
`qdrant_client.update_collection()` without rebuilding vectors.

---

## 4. Query Anti-Patterns Reviewed

| Pattern                        | Found? | Location                        | Status    |
| ------------------------------ | ------ | ------------------------------- | --------- |
| N+1 queries                    | Fixed  | `get_bulk_summary_stats()`      | ✅ Bulk query |
| Missing selectinload           | No     | All repos use selectinload      | ✅ OK     |
| Unbounded SELECT *             | No     | All queries have LIMIT          | ✅ OK     |
| Missing COUNT optimization     | No     | count() uses select_from()      | ✅ OK     |
| Unnecessary eager loading      | No     | Lazy by default, opt-in eager   | ✅ OK     |
| Session leak                   | No     | `get_async_session()` + try/finally | ✅ OK |

---

## 5. Summary of Changes

| Change                                  | File                                   |
| --------------------------------------- | -------------------------------------- |
| Pool sizing: 10+20 → 5+10 (per worker) | `backend/app/config.py`                |
| 5 new indexes for hot paths             | `backend/alembic/versions/002_*.py`    |
| Performance test suite (Locust)         | `backend/tests/performance/locustfile.py` |
| This tuning review document             | `docs/db-tuning-review.md`             |
