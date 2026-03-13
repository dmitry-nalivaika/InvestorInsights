# Testing Strategy — Detailed Test Specifications

> Referenced from [System Specification — §16 Testing Strategy](../system_specification.md#16-testing-strategy)

---

## Table of Contents

- [1. Testing Pyramid](#1-testing-pyramid)
- [2. Unit Tests](#2-unit-tests)
  - [2.1 Section Splitter](#21-section-splitter)
  - [2.2 Text Chunker](#22-text-chunker)
  - [2.3 Financial Formulas](#23-financial-formulas)
  - [2.4 Custom Formula Parser](#24-custom-formula-parser)
  - [2.5 Trend Detection](#25-trend-detection)
  - [2.6 Threshold Evaluator](#26-threshold-evaluator)
  - [2.7 Scoring Engine](#27-scoring-engine)
  - [2.8 Document Parser](#28-document-parser)
  - [2.9 XBRL Data Mapper](#29-xbrl-data-mapper)
  - [2.10 SEC EDGAR Client](#210-sec-edgar-client)
  - [2.11 Chat Prompt Builder](#211-chat-prompt-builder)
- [3. Integration Tests](#3-integration-tests)
  - [3.1 Company API](#31-company-api)
  - [3.2 Document Upload](#32-document-upload)
  - [3.3 Ingestion Pipeline](#33-ingestion-pipeline)
  - [3.4 Chat](#34-chat)
  - [3.5 Analysis](#35-analysis)
  - [3.6 Financial Data](#36-financial-data)
  - [3.7 Cross-Cutting (Auth, Health)](#37-cross-cutting)
- [4. End-to-End Tests](#4-end-to-end-tests)
- [5. Performance Tests](#5-performance-tests)
- [6. Test Data & Fixtures](#6-test-data--fixtures)
- [7. CI/CD Pipeline](#7-cicd-pipeline)
- [8. Test Configuration](#8-test-configuration)

---

## 1. Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E (5%)  │    Playwright / Cypress
                    │   Tests     │    Critical user journeys
                    ├─────────────┤
                 ┌──┤ Integration │    pytest + testcontainers
                 │  │  Tests (25%)│    API → DB → Vector Store
                 │  ├─────────────┤
              ┌──┤  │   Unit      │    pytest + pytest-asyncio
              │  │  │  Tests (70%)│    Pure logic, mocked deps
              │  │  └─────────────┘
              │  │
              └──┘
```

- **Framework:** pytest + pytest-asyncio
- **Mocking:** unittest.mock / pytest-mock
- **Coverage target:** 85% line coverage minimum

---

## 2. Unit Tests

### 2.1 Section Splitter

**File:** `tests/unit/test_section_splitter.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_split_10k_all_sections_present` | Sample 10-K full text with all 15 items | 15 Section objects with correct keys and content |
| `test_split_10k_missing_sections` | 10-K missing Items 6 and 9B | 13 sections, missing ones not in output |
| `test_split_handles_table_of_contents_duplicates` | 10-K where Item 1A appears in TOC and body | Section starts at body occurrence, not TOC |
| `test_split_10q_sections` | Sample 10-Q text | Correct Part I / Part II section split |
| `test_split_unknown_doc_type_returns_full_text` | doc_type="OTHER", any text | Single section with full text |
| `test_section_content_is_trimmed` | — | No leading/trailing whitespace in section content |
| `test_section_key_format` | — | All section_keys match pattern `item_[0-9]+[a-z]?` |

### 2.2 Text Chunker

**File:** `tests/unit/test_chunker.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_chunk_short_text_returns_single_chunk` | Text with 100 tokens | 1 chunk, content == input |
| `test_chunk_long_text_returns_multiple_chunks` | Text with 3000 tokens | ~4–5 chunks of ~768 tokens each |
| `test_chunk_overlap_content` | Text with 2000 tokens, overlap=128 | End of chunk N overlaps with start of chunk N+1 |
| `test_chunk_preserves_paragraph_boundaries` | Text with clear paragraph breaks | Chunks break at paragraph boundaries when possible |
| `test_chunk_metadata_propagation` | Text with metadata dict | All chunks carry the same metadata |
| `test_chunk_token_count_accuracy` | — | Reported token_count matches tiktoken encoding |
| `test_empty_text_returns_empty_list` | `""` | `[]` |

### 2.3 Financial Formulas

**File:** `tests/unit/test_formulas.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_gross_margin_calculation` | revenue=100M, gross_profit=40M | 0.40 |
| `test_gross_margin_zero_revenue` | revenue=0, gross_profit=0 | `None` |
| `test_roe_calculation` | net_income=10M, total_equity=50M | 0.20 |
| `test_roe_negative_equity` | net_income=10M, total_equity=-5M | -2.0 (valid, indicates issue) |
| `test_debt_to_equity` | long_term_debt=30M, total_equity=60M | 0.50 |
| `test_debt_to_equity_zero_equity` | long_term_debt=30M, total_equity=0 | `None` (division by zero handled) |
| `test_current_ratio` | total_current_assets=80M, total_current_liabilities=40M | 2.0 |
| `test_free_cash_flow_margin` | operating_cash_flow=50M, capital_expenditure=-10M, revenue=200M | 0.20 |
| `test_revenue_growth_rate` | revenue_current=120M, revenue_prior=100M | 0.20 |
| `test_revenue_growth_rate_prior_zero` | revenue_current=120M, revenue_prior=0 | `None` |
| `test_all_builtin_formulas_registered` | — | FormulaRegistry contains at least 25 entries |
| `test_formula_registry_get_unknown_formula` | formula_name="nonexistent" | Raises `FormulaNotFoundError` |
| `test_formula_required_fields_documented` | — | Every registered formula declares `required_fields` list |
| `test_roic_calculation` | operating_income=25M, total_assets=200M, current_liabilities=50M, cash=20M | 25M × (1−0.21) / (200M − 50M − 20M) ≈ 0.1519 |
| `test_interest_coverage_ratio` | operating_income=30M, interest_expense=5M | 6.0 |
| `test_interest_coverage_zero_interest` | operating_income=30M, interest_expense=0 | `None` |

### 2.4 Custom Formula Parser

**File:** `tests/unit/test_formula_parser.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_parse_simple_division` | `"income_statement.net_income / balance_sheet.total_equity"` | AST with Division node, two FieldRef leaves |
| `test_parse_nested_parentheses` | `"(a + b) * (c - d)"` | Correct operator precedence in AST |
| `test_parse_function_call_abs` | `"abs(cash_flow.capital_expenditure)"` | AST with FunctionCall(abs, [FieldRef]) |
| `test_parse_prev_reference` | `"prev(income_statement.revenue)"` | PrevRef node with lookback=1 |
| `test_parse_prev_reference_with_lookback` | `"prev(income_statement.revenue, 3)"` | PrevRef node with lookback=3 |
| `test_parse_complex_expression` | `"(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)"` | Valid AST computing YoY revenue growth |
| `test_parse_invalid_field_name` | `"nonexistent_statement.foo / bar"` | Raises `FormulaParseError` with field error |
| `test_parse_unbalanced_parentheses` | `"(a + b * c"` | Raises `FormulaParseError` mentioning parentheses |
| `test_parse_empty_expression` | `""` | Raises `FormulaParseError` |
| `test_parse_division_by_literal_zero` | `"income_statement.revenue / 0"` | Raises `FormulaParseError` or returns null at eval time |
| `test_evaluate_simple_expression` | expression=`"income_statement.revenue * 0.5"`, data={revenue: 100M} | 50M |
| `test_evaluate_with_missing_field` | Expression referencing field not in data | `None` (not crash) |
| `test_evaluate_prev_with_prior_data` | current={revenue: 120M}, prior={revenue: 100M} | `prev(revenue)` resolves to 100M |
| `test_evaluate_prev_without_prior_data` | current={revenue: 120M}, prior=None | `None` |

### 2.5 Trend Detection

**File:** `tests/unit/test_trend_detection.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_strong_upward_trend` | {2020: 10, 2021: 15, 2022: 20, 2023: 25, 2024: 30} | `"improving"` |
| `test_strong_downward_trend` | {2020: 30, 2021: 25, 2022: 20, 2023: 15, 2024: 10} | `"declining"` |
| `test_stable_values` | {2020: 10.0, 2021: 10.1, 2022: 9.9, 2023: 10.0, 2024: 10.2} | `"stable"` |
| `test_insufficient_data_points` | {2023: 10, 2024: 12} | `"insufficient_data"` |
| `test_all_null_values` | {2020: None, 2021: None, 2022: None} | `"insufficient_data"` |
| `test_mixed_null_values` | {2020: 10, 2021: None, 2022: 15, 2023: None, 2024: 20} | `"improving"` (nulls ignored, 3 valid points) |
| `test_single_data_point` | {2024: 42} | `"insufficient_data"` |
| `test_negative_values_declining` | {2020: -5, 2021: -10, 2022: -15, 2023: -20} | `"declining"` (values getting more negative) |
| `test_volatile_but_flat` | {2020: 10, 2021: 20, 2022: 5, 2023: 25, 2024: 10} | `"stable"` (no clear directional trend) |

### 2.6 Threshold Evaluator

**File:** `tests/unit/test_threshold_evaluator.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_greater_than_pass` | value=0.20, comparison=`">"`, threshold=0.15 | passed=True |
| `test_greater_than_fail` | value=0.10, comparison=`">"`, threshold=0.15 | passed=False |
| `test_greater_than_equal_boundary` | value=0.15, comparison=`">="`, threshold=0.15 | passed=True |
| `test_less_than` | value=0.30, comparison=`"<"`, threshold=0.50 | passed=True |
| `test_between_inclusive` | value=0.25, comparison=`"between"`, low=0.20, high=0.30 | passed=True |
| `test_between_at_boundary` | value=0.20, comparison=`"between"`, low=0.20, high=0.30 | passed=True |
| `test_between_outside` | value=0.35, comparison=`"between"`, low=0.20, high=0.30 | passed=False |
| `test_trend_up_with_improving` | trend=`"improving"`, comparison=`"trend_up"` | passed=True |
| `test_trend_up_with_declining` | trend=`"declining"`, comparison=`"trend_up"` | passed=False |
| `test_trend_up_with_stable` | trend=`"stable"`, comparison=`"trend_up"` | passed=False |
| `test_null_value` | value=None, comparison=`">"`, threshold=0.15 | passed=None, note=`"no_data"` |

### 2.7 Scoring Engine

**File:** `tests/unit/test_scoring.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_all_criteria_pass` | 5 criteria, all pass, weights=[1,1,1,1,1] | score=5, max=5, pct=100.0 |
| `test_all_criteria_fail` | 5 criteria, all fail, weights=[1,1,1,1,1] | score=0, max=5, pct=0.0 |
| `test_mixed_pass_fail` | 3 pass, 2 fail, weights=[1,2,1,2,1] | score=4, max=7, pct≈57.14 |
| `test_weighted_scoring` | criterion A (weight=3, pass), criterion B (weight=1, fail) | score=3, max=4, pct=75.0 |
| `test_no_data_excluded_from_max` | 3 criteria, 2 pass, 1 no_data | max=2 (not 3), score=2, pct=100.0 |
| `test_all_no_data` | 3 criteria, all no_data | max=0, score=0, pct=0 (or "N/A") |
| `test_disabled_criteria_excluded` | 3 criteria, 1 disabled | Only 2 criteria evaluated |
| `test_grade_assignment` | — | 95→A, 80→B, 65→C, 45→D, 30→F |

### 2.8 Document Parser

**File:** `tests/unit/test_document_parser.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_parse_simple_pdf` | `fixtures/simple_10k.pdf` | Extracted text length > 0, paragraphs preserved |
| `test_parse_html_filing` | `fixtures/sample_10k.html` | Clean text, tables converted to markdown |
| `test_parse_html_strips_style_tags` | HTML with `<style>` and `<script>` blocks | No CSS or JS in output |
| `test_parse_html_preserves_tables` | HTML with financial data tables | Pipe-delimited markdown table in output |
| `test_clean_text_normalizes_whitespace` | Text with `\xa0`, multiple spaces, `\r\n` | Normalized to standard spaces and `\n` |
| `test_clean_text_removes_page_numbers` | Text with "Page 42 of 215" patterns | Page number lines removed |
| `test_unsupported_format_raises_error` | `file.docx` | Raises `UnsupportedFormatError` |

### 2.9 XBRL Data Mapper

**File:** `tests/unit/test_xbrl_mapper.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_map_revenue_tag` | XBRL tag `"us-gaap:Revenues"` with value 394328000000 | Maps to `income_statement.revenue` |
| `test_map_alternative_revenue_tag` | XBRL tag `"us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"` | Maps to `income_statement.revenue` (alternative tag) |
| `test_map_balance_sheet_tags` | Fixture of XBRL balance sheet tags | All key `balance_sheet` fields populated |
| `test_handle_unknown_tag` | XBRL tag `"us-gaap:SomeObscureTag"` | Ignored (not in mapping), no error |
| `test_select_correct_period` | XBRL facts with multiple period values | Selects annual (12 month) or quarterly (3 month) correctly |
| `test_handle_missing_required_tags` | XBRL data missing revenue | `income_statement.revenue = None`, warning logged |
| `test_full_company_facts_parsing` | `fixtures/apple_companyfacts_sample.json` | Multiple years of complete financial data |

### 2.10 SEC EDGAR Client

**File:** `tests/unit/test_sec_client.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_resolve_cik_from_ticker` | `"AAPL"` (mocked response) | CIK=`"0000320193"` |
| `test_resolve_unknown_ticker` | `"XYZNOTREAL"` | Raises `TickerNotFoundError` |
| `test_get_filing_index` | CIK, filing_type=`"10-K"`, count=10 | List of filing metadata dicts |
| `test_rate_limiting_applied` | — | Requests spaced at least 100ms apart |
| `test_user_agent_header_set` | — | All requests include `User-Agent` with email |

### 2.11 Chat Prompt Builder

**File:** `tests/unit/test_prompt_builder.py`

| Test | Input | Expected |
|------|-------|----------|
| `test_system_prompt_contains_company_info` | company={ticker: "AAPL", name: "Apple Inc"} | System prompt contains "Apple Inc" and "AAPL" |
| `test_system_prompt_contains_filing_range` | earliest_year=2015, latest_year=2024 | System prompt mentions 2015 and 2024 |
| `test_context_injection_format` | 3 retrieved chunks with metadata | Formatted with source headers and separator lines |
| `test_context_token_budget_respected` | 30 chunks totaling 50000 tokens, budget=12000 | Only top chunks fitting within 12000 tokens included |
| `test_history_included_in_messages` | 5 previous exchanges | Messages array includes all 10 messages (5 user + 5 assistant) |
| `test_history_truncation` | 20 previous exchanges, max_history=10 | Only last 10 exchanges included |
| `test_empty_context_produces_no_context_message` | 0 retrieved chunks | Message includes note about no relevant filings found |

---

## 3. Integration Tests

**Framework:** pytest + testcontainers (Docker-based)

**Environment:**

| Service | Image |
|---------|-------|
| PostgreSQL | `testcontainers postgres:16-alpine` |
| Qdrant | `testcontainers qdrant/qdrant:v1.9.7` |
| Redis | `testcontainers redis:7-alpine` |
| Azure Blob Storage | `testcontainers mcr.microsoft.com/azure-storage/azurite:latest` |
| LLM API | Mocked via httpx respx or VCR.py |
| SEC API | Mocked via httpx respx with recorded fixtures |

**Fixtures:**

- **Sample companies:** `TEST` (Test Corp, CIK 0001234567), `SMPL` (Sample Inc, CIK 0009876543)
- **Sample documents:** `test_corp_10k_2024.pdf`, `test_corp_10k_2023.pdf`, `test_corp_10q_2024_q1.html`
- **Sample XBRL:** `test_corp_companyfacts.json`
- **Sample embeddings:** Pre-computed, deterministic (not calling OpenAI in tests)

### 3.1 Company API

**File:** `tests/integration/test_company_api.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_create_company_success` | `POST /api/v1/companies {"ticker": "TEST"}` | Status 201; body contains id, ticker="TEST", name populated; DB has 1 row |
| `test_create_company_duplicate_ticker` | Create TEST, then `POST` TEST again | Status 409 |
| `test_list_companies_empty` | `GET /api/v1/companies` | Status 200, items=[], total=0 |
| `test_list_companies_with_data` | Create 3 companies → `GET` | Status 200, total=3 |
| `test_list_companies_search` | Create AAPL/MSFT/GOOGL → `GET ?search=app` | Returns only AAPL |
| `test_get_company_detail` | Create company + 2 documents → `GET /{id}` | Includes documents_summary.total=2 |
| `test_get_company_not_found` | `GET /{random_uuid}` | Status 404 |
| `test_delete_company_cascades` | Company with docs/chunks/financials/chats → `DELETE ?confirm=true` | Status 204; no rows in any table; Qdrant collection deleted; Blob Storage files removed |
| `test_delete_company_without_confirm` | `DELETE /{id}` (no confirm) | Status 400 |

### 3.2 Document Upload

**File:** `tests/integration/test_document_api.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_upload_pdf_document` | `POST` multipart with PDF | Status 202; Blob Storage file exists; DB row status="uploaded" |
| `test_upload_html_document` | `POST` with HTML file | Same as PDF test |
| `test_upload_duplicate_period` | Upload 10-K FY2024 twice | Status 409 |
| `test_upload_oversized_file` | `POST` with 60MB file | Status 413 |
| `test_upload_invalid_file_type` | `POST` with .docx file | Status 415 |
| `test_list_documents_for_company` | 5 docs for A, 3 for B → list A | Returns exactly 5 |
| `test_list_documents_filter_by_type` | 3 10-Ks + 2 10-Qs → filter `?doc_type=10-K` | Returns 3 |
| `test_delete_document_removes_chunks` | Process doc → delete | No chunks in DB; vectors removed from Qdrant; Blob Storage file removed |

### 3.3 Ingestion Pipeline

**File:** `tests/integration/test_ingestion_pipeline.py`

> **Note:** These tests run the actual pipeline against real (test fixture) files. OpenAI embedding calls are mocked with deterministic vectors.

| Test | Setup | Expected |
|------|-------|----------|
| `test_full_ingestion_pdf` | Upload PDF fixture | status="ready"; ≥5 sections; ≥20 chunks; Qdrant vectors match count |
| `test_full_ingestion_html` | Upload HTML fixture | Same as PDF |
| `test_ingestion_creates_financial_data` | Company with CIK + upload 10-K (mocked SEC API) | `financial_statements` has 1 row; IS/BS/CF populated |
| `test_ingestion_idempotent` | Re-run ingestion for same document | No duplicate chunks; same vector count |
| `test_ingestion_failure_marks_error` | Upload corrupt PDF | status="error"; error_message is meaningful |
| `test_ingestion_retry_after_failure` | Error state → `POST /retry` | status="ready" |
| `test_section_splitting_accuracy` | Upload fixture 10-K with known sections | Sections match expected section_keys |
| `test_chunk_overlap_verification` | Process document | For consecutive chunks in same section: last 128 tokens of chunk[i] == first 128 tokens of chunk[i+1] |

### 3.4 Chat

**File:** `tests/integration/test_chat_api.py`

> **Note:** LLM responses are mocked via httpx respx. Vector search uses real Qdrant with test data.

| Test | Action | Expected |
|------|--------|----------|
| `test_create_new_chat_session` | `POST /chat {"message": "What does the company do?"}` | SSE events: session, sources, tokens, done; DB: 1 session, 2 messages |
| `test_chat_returns_sources` | Question about risk factors | Sources event has chunks from `item_1a` sections |
| `test_chat_continues_existing_session` | Existing session → new message with session_id | Session now has 4 messages; same session_id |
| `test_chat_filters_by_doc_type` | `filter_doc_types=["10-K"]` | All sources from 10-K documents |
| `test_chat_filters_by_year` | `filter_year_min=2024, filter_year_max=2024` | All sources from FY2024 |
| `test_chat_with_no_ready_documents` | Company with 0 processed documents | Status 400 |
| `test_chat_session_list` | Create 3 sessions → list | 3 sessions, ordered by updated_at desc |
| `test_chat_session_history` | Session with 5 exchanges → get | 10 messages in chronological order |
| `test_delete_chat_session` | Session with messages → delete | Status 204; session and messages gone |

### 3.5 Analysis

**File:** `tests/integration/test_analysis_api.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_create_analysis_profile` | `POST /profiles` with 5 criteria | Status 201; DB has profile + 5 criteria |
| `test_create_profile_invalid_formula` | formula=`"nonexistent_formula"` | Status 422 |
| `test_create_profile_invalid_custom_formula` | formula=`"income_statement.foo / bar"` | Status 422 with field error |
| `test_run_analysis` | `POST /run` | Status 200; overall_score + criteria_results with values_by_year, passed, trend; DB has 1 result |
| `test_run_analysis_all_criteria_computable` | Company with complete data | No `"no_data"` criteria |
| `test_run_analysis_missing_financial_data` | Company with 1 year only | trend=`"insufficient_data"` for all; criteria still evaluated on available data |
| `test_run_analysis_multi_company` | 3 companies → `POST /run` | 3 result objects, each independently scored |
| `test_analysis_results_persistence` | Run → `GET /results?company_id=X` | Previous result retrievable |
| `test_update_profile_increments_version` | `PUT /profiles/{id}` | Version incremented; old results preserve old version |
| `test_list_builtin_formulas` | `GET /formulas` | ≥25 formulas with name, category, description, required_fields |

### 3.6 Financial Data

**File:** `tests/integration/test_financials_api.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_get_annual_financials` | 5 years data → `GET ?period=annual` | 5 period objects with IS/BS/CF |
| `test_get_quarterly_financials` | Quarterly data → `GET ?period=quarterly` | Quarterly periods returned |
| `test_filter_by_year_range` | `GET ?start_year=2022&end_year=2024` | Only 2022–2024 periods |
| `test_export_csv` | `GET /export` | content-type: text/csv; parseable; values match DB |

### 3.7 Cross-Cutting

**File:** `tests/integration/test_auth.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_valid_api_key` | Any endpoint with correct `X-API-Key` | Request succeeds |
| `test_missing_api_key` | `GET /companies` with no header | Status 401 |
| `test_invalid_api_key` | `GET /companies` with `X-API-Key="wrong"` | Status 401 |
| `test_health_endpoint_no_auth` | `GET /health` without API key | Status 200 (public) |

**File:** `tests/integration/test_health.py`

| Test | Action | Expected |
|------|--------|----------|
| `test_all_healthy` | All services up | Status 200, all components "healthy" |
| `test_database_down` | Stop postgres container | `database` shows "unhealthy" |
| `test_qdrant_down` | Stop qdrant container | `vector_store` shows "unhealthy" |

---

## 4. End-to-End Tests

**Framework:** Playwright (Python or TypeScript)  
**Browser:** Chromium  
**Environment:** Full docker-compose stack with mocked external APIs

> LLM and SEC APIs are mocked at the network level (mock server). Tests use realistic but small fixture files.

### Journey 1: Complete Company Setup

**File:** `tests/e2e/test_company_journey.py`  
**Timeout:** 120s

1. Navigate to `/companies`
2. Click "Add Company"
3. Enter ticker `"TEST"` in modal
4. Submit → company created, redirected to company page
5. Verify company header shows "Test Corp" (auto-resolved name)
6. Navigate to Documents tab
7. Click "Fetch from SEC"
8. Select "10-K" and "Last 2 years"
9. Submit → progress indicator shows
10. Wait for all documents to reach "ready" status (poll)
11. Navigate to Financials tab
12. Verify financial data table shows 2 years of data

**Assertions:**
- Company appears in sidebar after creation
- Documents tab shows correct filing count
- Financial data is populated for expected periods

### Journey 2: Manual Upload & Chat

**File:** `tests/e2e/test_upload_chat_journey.py`

1. Navigate to `/companies/{TEST}/documents`
2. Click "Upload Document"
3. Select fixture PDF, fill metadata (10-K, FY2024, etc.)
4. Submit → file uploads, processing begins
5. Wait for status = "ready"
6. Navigate to Chat tab
7. Click "New Chat"
8. Type "What are the main risk factors?"
9. Press Enter or click Send
10. Observe streaming response appearing token by token
11. Verify response contains filing citation
12. Expand sources section → verify source chips
13. Click on a source chip → see chunk text
14. Type follow-up: "How have these changed from last year?"
15. Observe response references multiple filing years
16. Navigate away and come back → session is preserved
17. Open session → full history visible

**Assertions:**
- Streaming works (text appears progressively)
- Citations reference correct document type and year
- Sources panel shows relevant sections
- Session persists across page navigation
- Chat history loads correctly

### Journey 3: Analysis Workflow

**File:** `tests/e2e/test_analysis_journey.py`

1. Navigate to `/analysis/profiles`
2. Click "Create Profile"
3. Name: "My Value Screen"
4. Add criterion: Gross Margin > 40%, weight 2, category profitability
5. Add criterion: Debt to Equity < 0.5, weight 1, category solvency
6. Add criterion: ROE > 15%, weight 3, category profitability
7. Save profile
8. Navigate to `/companies/{TEST}/analysis`
9. Select "My Value Screen" profile
10. Click "Run Analysis"
11. Loading spinner appears
12. Results load: score card, criteria table, AI summary
13. Verify score card shows overall percentage and grade
14. Verify criteria table shows values, thresholds, pass/fail coloring
15. Click on a criterion → trend chart appears
16. Scroll to AI summary → verify narrative is present

**Assertions:**
- Profile creation succeeds with validation
- Analysis runs and produces scored results
- Pass/fail colors are correct (green/red)
- Trend charts render with data points
- AI summary mentions company name

### Journey 4: Multi-Company Comparison

**File:** `tests/e2e/test_comparison_journey.py`

1. Navigate to `/analysis/compare`
2. Select 3 companies from multi-select dropdown
3. Select analysis profile
4. Click "Compare"
5. Comparison table loads with companies as columns
6. Verify each criterion row shows values for each company
7. Verify color coding (green for pass, red for fail)
8. Verify companies are ranked by overall score

**Assertions:**
- All 3 companies appear in comparison
- Ranking is correct (highest score first)
- Cell colors match pass/fail status

---

## 5. Performance Tests

**Framework:** locust (Python-based load testing)

### Ingestion Throughput

Submit 10 documents, measure time until all reach "ready".

- **Target:** < 5 minutes per document average
- **Measurements:** total_time_seconds, avg_time_per_document, max_time_per_document, peak_memory_usage

### Vector Search Latency

Pre-load Qdrant with N vectors, run 100 search queries.

| Vector Count | Target p50 | Target p99 |
|-------------|-----------|-----------|
| 10K | < 50ms | < 200ms |
| 100K | < 100ms | < 300ms |
| 500K | < 200ms | < 500ms |

### Analysis Computation

Run analysis with 30 criteria over 10 years for 1 company.

- **Target:** < 3 seconds
- **Measurements:** total_time_ms, per_criterion_time_ms, formula_evaluation_time_ms

### Concurrent API Load

Simulate 10 concurrent users doing mixed operations.

- **Target:** p95 < 500ms for non-streaming endpoints
- **Operation mix:** list companies (30%), get company detail (30%), get financial data (20%), list chat sessions (10%), run analysis (10%)

---

## 6. Test Data & Fixtures

**Directory:** `tests/fixtures/`

| Fixture | Description | Purpose |
|---------|-------------|---------|
| `simple_10k.pdf` | 10-page synthetic 10-K with all standard sections | Unit tests for parsing and splitting |
| `simple_10k.html` | HTML version of simple 10-K (SEC-style nested tables) | HTML parsing tests |
| `real_10k_excerpt.pdf` | 20-page excerpt from a real (public domain) 10-K | Realistic integration testing |
| `corrupt_file.pdf` | Intentionally corrupt PDF | Error handling tests |
| `large_10k.pdf` | 250-page realistic 10-K | Performance testing, chunking verification |
| `companyfacts_complete.json` | Complete SEC companyfacts API response (5 years) | XBRL mapping integration tests |
| `companyfacts_sparse.json` | Partial companyfacts with missing tags | Graceful handling of missing data |
| `test_financials_5y.json` | 5 years of statement_data JSON (FY2020–FY2024) | Formula computation and analysis tests |
| `chat_response_risk_factors.json` | Pre-recorded OpenAI streaming response | Chat integration tests (mocked LLM) |
| `chat_response_revenue_segments.json` | Pre-recorded response about revenue breakdown | Chat integration tests |
| `analysis_summary_response.json` | Pre-recorded analysis narrative summary | Analysis integration tests |
| `test_embeddings.npy` | Pre-computed 3072-dim embeddings (100 vectors) | Vector search tests without calling OpenAI |
| `edgar_company_tickers.json` | Mocked SEC company tickers lookup | CIK resolution tests |
| `edgar_submissions.json` | Mocked SEC submissions API response | Filing fetch tests |

**Generation script:** `tests/fixtures/generate_fixtures.py` — generates all synthetic test fixtures deterministically. Run once to create, commit to repo. Allows regeneration if schema changes.

---

## 7. CI/CD Pipeline

**Platform:** GitHub Actions

**Triggers:** push to main, pull request to main, manual trigger

### Jobs

#### `lint-and-typecheck`

```yaml
steps:
  - checkout
  - setup python 3.12
  - install dependencies
  - run: ruff check backend/
  - run: ruff format --check backend/
  - run: mypy backend/app/ --strict
  - setup node 20
  - run: cd frontend && npm ci
  - run: cd frontend && npm run lint
  - run: cd frontend && npm run type-check
```

#### `unit-tests`

```yaml
steps:
  - checkout
  - setup python 3.12
  - install dependencies
  - run: pytest tests/unit/ -v --cov=app --cov-report=xml --cov-fail-under=85
  - upload coverage report
```

#### `integration-tests`

```yaml
services:
  postgres: postgres:16-alpine
  redis: redis:7-alpine
  qdrant: qdrant/qdrant:v1.9.7
  azurite: mcr.microsoft.com/azure-storage/azurite:latest
env:
  DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
  QDRANT_URL: http://localhost:6333
  REDIS_URL: redis://localhost:6379/0
  AZURE_STORAGE_CONNECTION_STRING: DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;
  LLM_PROVIDER: azure_openai
  AZURE_OPENAI_API_KEY: sk-test-mock    # mocked, not real
  AZURE_OPENAI_ENDPOINT: https://mock.openai.azure.com/
steps:
  - checkout
  - setup python 3.12
  - install dependencies
  - run migrations
  - run: pytest tests/integration/ -v --timeout=120
```

#### `frontend-tests`

```yaml
steps:
  - checkout
  - setup node 20
  - run: cd frontend && npm ci
  - run: cd frontend && npm run test -- --coverage
  - run: cd frontend && npm run build
```

#### `e2e-tests`

```yaml
needs: [unit-tests, integration-tests, frontend-tests]
steps:
  - checkout
  - docker compose -f docker-compose.dev.yml up -d
  - wait for health check
  - setup playwright
  - run: pytest tests/e2e/ -v --timeout=300
  - docker compose -f docker-compose.dev.yml down
artifacts:
  - playwright traces and screenshots on failure
```

#### `build-images`

```yaml
needs: [e2e-tests]
if: github.ref == 'refs/heads/main'
steps:
  - checkout
  - az login (via OIDC federated credentials)
  - az acr login --name ${ACR_NAME}
  - build backend Docker image
  - build frontend Docker image
  - docker push ${ACR_NAME}.azurecr.io/investorinsights-api:${GITHUB_SHA}
  - docker push ${ACR_NAME}.azurecr.io/investorinsights-frontend:${GITHUB_SHA}
```

#### `deploy-staging` (optional)

```yaml
needs: [build-images]
if: github.ref == 'refs/heads/main'
environment: staging
steps:
  - az login (via OIDC federated credentials)
  - az containerapp update --name api --resource-group rg-investorinsights-staging --image ...
  - az containerapp update --name worker --resource-group rg-investorinsights-staging --image ...
  - az containerapp update --name frontend --resource-group rg-investorinsights-staging --image ...
  - wait for health checks to pass
```

---

## 8. Test Configuration

```toml
# pyproject.toml

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: unit tests (no external dependencies)",
    "integration: integration tests (require Docker services)",
    "e2e: end-to-end tests (require full stack)",
    "slow: tests that take > 30 seconds",
    "performance: performance/load tests",
]
filterwarnings = [
    "ignore::DeprecationWarning:sqlalchemy.*",
]
timeout = 30
timeout_method = "signal"
```

**Quick reference:**

```bash
# Run unit tests only
pytest -m unit

# Run integration only
pytest -m integration

# Run everything except e2e
pytest -m "not e2e"

# Run with coverage
pytest -m "unit or integration" --cov=app
```
