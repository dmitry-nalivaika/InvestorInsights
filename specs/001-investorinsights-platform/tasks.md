# Tasks: InvestorInsights Platform

**Input**: Design documents from `/specs/001-investorinsights-platform/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/api-spec.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/app/`, `frontend/src/`
- **Tests**: `backend/tests/`, `frontend/tests/`
- **Infra**: `infra/`
- Paths based on plan.md Project Structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, Azure infrastructure, and basic application skeleton

- [ ] T001 [P] Create project structure per plan.md — monorepo with `backend/`, `frontend/`, `infra/`, `scripts/`
- [ ] T002 [P] Azure infrastructure provisioning via Bicep IaC in `infra/main.bicep` (Resource Group, PostgreSQL B1ms, Blob Storage, Key Vault, ACR, Log Analytics, App Insights, OpenAI, Container Apps env)
- [ ] T003 [P] Bicep parameter files — `infra/parameters/dev.bicepparam` (budget-optimised) and `infra/parameters/prod.bicepparam` (full)
- [ ] T003a [P] Infrastructure operational scripts — `infra/scripts/deploy.sh`, `infra/scripts/destroy.sh`, `infra/scripts/seed-keyvault.sh` per plan.md IaC layout
- [ ] T004 [P] Docker Compose for local development in `docker-compose.dev.yml` (PostgreSQL, Redis, Qdrant, Azurite)
- [ ] T005 FastAPI application skeleton with Uvicorn in `backend/app/main.py`, config loading
- [ ] T006 [P] Pydantic `BaseSettings` configuration validation in `backend/app/config.py`
- [ ] T007 [P] Structured logging setup — structlog + OpenTelemetry → Application Insights
- [ ] T008 PostgreSQL schema + Alembic migration setup in `backend/alembic/versions/001_initial_schema.py`
- [ ] T009 SQLAlchemy ORM models for all entities in `backend/app/models/`
- [ ] T010 [P] Pydantic request/response schemas in `backend/app/schemas/`
- [ ] T011 [P] Azure Blob Storage client integration in `backend/app/clients/storage_client.py`
- [ ] T012 Authentication middleware (API key from Key Vault, `X-API-Key` header) in `backend/app/api/middleware/`
- [ ] T013 [P] Error handling middleware (global exception handler, error taxonomy) in `backend/app/api/middleware/`
- [ ] T014 Health check endpoint (`GET /api/v1/health` — ping DB, Redis, Qdrant, Blob) in `backend/app/api/health.py`
- [ ] T015 [P] Makefile with common commands (setup, up, down, test, lint, migrate, azure-*)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T016 Qdrant client wrapper with collection management in `backend/app/clients/qdrant_client.py`
- [ ] T017 [P] Redis client wrapper in `backend/app/clients/redis_client.py`
- [ ] T018 Celery worker setup with Redis broker, ingestion/analysis/sec_fetch queues in `backend/app/worker/`
- [ ] T019 [P] SEC EDGAR base client (HTTP with rate limiting, User-Agent) in `backend/app/clients/sec_client.py`
- [ ] T020 [P] Azure OpenAI client wrapper (embeddings + chat) in `backend/app/clients/openai_client.py`

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Register & Browse Companies (Priority: P1) 🎯 MVP

**Goal**: An analyst can register a company by ticker and see it in their tracked company list with auto-resolved metadata.

**Independent Test**: Register "AAPL" → company appears in list with auto-resolved name, CIK, sector.

### Implementation for User Story 1

- [ ] T100 [P] [US1] Company repository (data access layer) in `backend/app/services/company_repository.py`
- [ ] T101 [P] [US1] SEC EDGAR client — ticker → CIK resolution, company metadata lookup in `backend/app/clients/sec_client.py`
- [ ] T102 [US1] Company service (business logic, auto-resolve from SEC) in `backend/app/services/company_service.py` (depends on T100, T101)
- [ ] T103 [US1] Company CRUD API — `POST/GET/PUT/DELETE /api/v1/companies` in `backend/app/api/companies.py`
- [ ] T104 [US1] Unique ticker constraint enforcement (409 on duplicate)
- [ ] T105 [US1] Company list with summary statistics (doc count, latest filing, readiness %) in `backend/app/api/companies.py`
- [ ] T106 [US1] Company delete with CASCADE cleanup (all associated data) in `backend/app/services/company_service.py`
- [ ] T109 [US1] Company metadata update — `PUT /api/v1/companies/{id}` partial update (name, sector, industry, description override) in `backend/app/api/companies.py` (FR-104)
- [ ] T110 [US1] Company search and filter — query params `?search=` (ticker, name) and `?sector=` on list endpoint in `backend/app/api/companies.py` (FR-106)

### Tests for User Story 1

- [ ] T107 [P] [US1] Unit tests — company service, SEC client (mocked) in `backend/tests/unit/test_company_service.py`
- [ ] T108 [P] [US1] Integration tests — company CRUD API against test DB in `backend/tests/integration/test_companies_api.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Upload & Ingest SEC Filings (Priority: P1)

**Goal**: An analyst can upload SEC filings or auto-fetch from EDGAR. The system parses, chunks, embeds, and extracts financial data — making them available for chat and analysis.

**Independent Test**: Upload a 10-K PDF → status progresses through uploaded → parsing → embedding → ready. Chunks appear in vector store. Financial data extracted via XBRL.

### Implementation for User Story 2 — Document Ingestion

- [ ] T200 [P] [US2] Document upload API — `POST /api/v1/companies/{id}/documents` (multipart) in `backend/app/api/documents.py`
- [ ] T201 [P] [US2] File storage in Azure Blob Storage (organised by company/type/year) in `backend/app/services/document_service.py`
- [ ] T202 [US2] Document status state machine (uploaded → parsing → parsed → embedding → ready → error) in `backend/app/models/document.py`
- [ ] T203 [US2] Duplicate upload prevention (409 for same company + type + year + quarter) in `backend/app/services/document_service.py`
- [ ] T204 [P] [US2] PDF text extraction — PyMuPDF parser in `backend/app/ingestion/pdf_parser.py`
- [ ] T205 [P] [US2] HTML text extraction — BeautifulSoup + custom cleaner in `backend/app/ingestion/html_parser.py`
- [ ] T206 [US2] Text cleaning and normalisation (Unicode, whitespace, headers/footers, tables → markdown) in `backend/app/ingestion/text_cleaner.py`
- [ ] T207 [US2] Section splitter — regex-based for 10-K Items (1, 1A, 1B, 1C, 2, 3, 5, 6, 7, 7A, 8, 9A) and 10-Q in `backend/app/ingestion/section_splitter.py`
- [ ] T208 [US2] Text chunker — recursive character splitter (768 tokens, 128 overlap, tiktoken) in `backend/app/ingestion/chunker.py`
- [ ] T209 [US2] Qdrant collection management — create per-company collection (3072 dims, cosine) in `backend/app/clients/qdrant_client.py`
- [ ] T210 [US2] Azure OpenAI embedding integration — batch embed chunks (text-embedding-3-large) in `backend/app/ingestion/embedder.py`
- [ ] T211 [US2] Vector upsert to Qdrant with metadata payload in `backend/app/ingestion/embedder.py`
- [ ] T212 [US2] Ingestion pipeline orchestrator — coordinates all stages, updates status in `backend/app/ingestion/pipeline.py` (depends on T204–T211)
- [ ] T213 [US2] Corrupt file handling — graceful error with clear message in `backend/app/ingestion/pipeline.py`
- [ ] T214 [US2] Document retry API — `POST /api/v1/documents/{id}/retry` (re-run from failed stage) in `backend/app/api/documents.py`
- [ ] T215 [US2] Document delete with cascade — remove file, vectors, sections, chunks, financials in `backend/app/services/document_service.py`

### Implementation for User Story 2 — SEC EDGAR Integration

- [ ] T300 [P] [US2] SEC EDGAR filing index fetcher — list available filings for company/CIK in `backend/app/clients/sec_client.py`
- [ ] T301 [P] [US2] SEC EDGAR filing downloader — fetch actual filing documents in `backend/app/clients/sec_client.py`
- [ ] T302 [US2] SEC API rate limiter integration test — verify 10 req/s enforcement and User-Agent header from T019 in `backend/app/clients/sec_client.py`
- [ ] T303 [P] [US2] XBRL `companyfacts` API integration — fetch structured financial data in `backend/app/clients/sec_xbrl_client.py`
- [ ] T304 [US2] XBRL tag → internal schema mapper (60+ US-GAAP tags) in `backend/app/ingestion/xbrl_mapper.py`
- [ ] T305 [US2] Financial statements storage in PostgreSQL (JSONB `statement_data`) in `backend/app/services/financial_service.py`
- [ ] T306 [US2] Auto-fetch API — `POST /api/v1/companies/{id}/documents/fetch-sec` in `backend/app/api/documents.py`
- [ ] T307 [US2] Celery queue for SEC fetch tasks (skip duplicates, progress tracking) in `backend/app/worker/tasks/sec_fetch.py`
- [ ] T308 [US2] Async task status API — `GET /api/v1/tasks/{task_id}` in `backend/app/api/tasks.py`

### Implementation for User Story 2 — Financial Data API (also serves US6)

- [ ] T309 [US2] Financial data API — `GET /api/v1/companies/{id}/financials` in `backend/app/api/financials.py`
- [ ] T310 [P] [US2] CSV export — `GET /api/v1/companies/{id}/financials/export` in `backend/app/api/financials.py`

### Tests for User Story 2

- [ ] T311 [P] [US2] Unit tests — parser, splitter, chunker, cleaner, XBRL mapper in `backend/tests/unit/test_ingestion.py`
- [ ] T312 [P] [US2] Integration tests — full pipeline (upload → ready) in `backend/tests/integration/test_ingestion_pipeline.py`
- [ ] T313 [P] [US2] Integration tests — SEC fetch + XBRL extract flow in `backend/tests/integration/test_sec_fetch.py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Chat with AI About Company Filings (Priority: P1)

**Goal**: An analyst can start a chat session scoped to a company and ask qualitative questions about its SEC filings, receiving streaming answers with source citations.

**Independent Test**: Ask "What are the main risk factors?" → receive a streaming response citing specific filings, with source chunks displayed.

### Implementation for User Story 3

- [ ] T400 [P] [US3] Chat session management — create, list, get, delete in `backend/app/services/chat_service.py`
- [ ] T401 [P] [US3] Chat message persistence (role, content, sources, token_count) in `backend/app/services/chat_service.py`
- [ ] T402 [US3] Vector similarity search — query embedding + Qdrant search with metadata filters in `backend/app/services/retrieval_service.py`
- [ ] T403 [US3] System prompt builder — company-specific prompt with rules in `backend/app/services/chat_agent.py`
- [ ] T404 [US3] Context assembly — retrieved chunks + conversation history within token budget in `backend/app/services/chat_agent.py` (depends on T402, T403)
- [ ] T405 [US3] Azure OpenAI chat completion with streaming (SSE, with direct OpenAI fallback) in `backend/app/clients/openai_client.py`
- [ ] T406 [US3] SSE endpoint — `POST /api/v1/companies/{id}/chat` with event types: session, sources, token, done, error in `backend/app/api/chat.py`
- [ ] T407 [US3] Source citation extraction and formatting in `backend/app/services/chat_agent.py`
- [ ] T408 [US3] Conversation history management (last N exchanges, configurable, token budget) in `backend/app/services/chat_service.py`
- [ ] T409 [P] [US3] Session title auto-generation (from first user message) in `backend/app/services/chat_service.py`
- [ ] T410 [US3] Retrieval config support (top_k, score_threshold, doc_type/year/section filters) in `backend/app/services/retrieval_service.py`
- [ ] T415 [US3] LLM-based query expansion — generate 2–3 alternative queries to improve retrieval recall in `backend/app/services/retrieval_service.py` (FR-409)
- [ ] T411 [US3] No-results handling — inform user, suggest rephrasing in `backend/app/services/chat_agent.py`
- [ ] T412 [US3] Out-of-scope refusal (predictions, buy/sell, unrelated topics) in `backend/app/services/chat_agent.py`

### Tests for User Story 3

- [ ] T413 [P] [US3] Unit tests — prompt builder, retrieval logic, context assembly in `backend/tests/unit/test_chat_agent.py`
- [ ] T414 [P] [US3] Integration tests — full chat flow (mocked LLM) in `backend/tests/integration/test_chat_api.py`

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently — core MVP complete

---

## Phase 6: User Story 4 - Score Companies with Analysis Profiles (Priority: P2)

**Goal**: An analyst can create a custom analysis profile and run it against a company to see a scored report card with pass/fail per criterion, trends, and AI summary.

**Independent Test**: Create a "Value Investor" profile with 10 criteria → run against AAPL → see scored results with pass/fail, trend arrows, and AI summary.

### Implementation for User Story 4

- [ ] T500 [P] [US4] Formula registry — 25+ built-in formulas (profitability, growth, liquidity, solvency, efficiency, cash flow, dividend) in `backend/app/analysis/formulas.py`
- [ ] T501 [P] [US4] Custom formula expression parser (lexer + recursive descent parser + evaluator) in `backend/app/analysis/expression_parser.py`
- [ ] T502 [US4] `prev()` reference resolution — previous period data lookback in `backend/app/analysis/expression_parser.py`
- [ ] T503 [US4] Formula validation at save time (field references, balanced parens, syntax) in `backend/app/analysis/expression_parser.py`
- [ ] T504 [US4] Analysis profile CRUD API — `POST/GET/PUT/DELETE /api/v1/analysis/profiles` in `backend/app/api/analysis.py`
- [ ] T505 [US4] Analysis criteria management (1–30 per profile, with category, formula, comparison, threshold, weight, lookback) in `backend/app/services/analysis_service.py`
- [ ] T506 [US4] Analysis execution engine — load financials, compute formulas across years, evaluate thresholds in `backend/app/analysis/engine.py` (depends on T500, T501)
- [ ] T507 [US4] Trend detection — OLS linear regression (improving/declining/stable, min 3 data points) in `backend/app/analysis/trend.py`
- [ ] T508 [US4] Scoring — binary pass/fail × weight, null handling (no_data excluded from max), grade A–F in `backend/app/analysis/scorer.py`
- [ ] T509 [US4] Analysis run API — `POST /api/v1/analysis/run` (1–10 companies × 1 profile) in `backend/app/api/analysis.py`
- [ ] T510 [US4] Analysis results persistence (JSONB result_details, overall/max/pct scores) in `backend/app/services/analysis_service.py`
- [ ] T511 [US4] AI narrative summary generation via LLM (strengths, concerns, data gaps) in `backend/app/services/analysis_service.py`
- [ ] T512 [US4] Analysis results API — `GET /api/v1/analysis/results`, `GET /api/v1/analysis/results/{id}` in `backend/app/api/analysis.py`
- [ ] T513 [P] [US4] Built-in formulas list API — `GET /api/v1/analysis/formulas` in `backend/app/api/analysis.py`
- [ ] T517 [US4] Analysis results JSON export — `GET /api/v1/analysis/results/{id}/export` returns full result as downloadable JSON in `backend/app/api/analysis.py` (FR-601)
- [ ] T514 [P] [US4] Default analysis profile seeding (Quality Value Investor, 15 criteria) in `backend/scripts/seed_profiles.py`

### Tests for User Story 4

- [ ] T515 [P] [US4] Unit tests — all 25+ formulas, parser, scorer, trend detection, threshold evaluator in `backend/tests/unit/test_analysis.py`
- [ ] T516 [P] [US4] Integration tests — full analysis flow in `backend/tests/integration/test_analysis_api.py`

**Checkpoint**: At this point, User Stories 1–4 should all be independently functional

---

## Phase 7: User Story 5 - Compare Companies Side by Side (Priority: P3)

**Goal**: An analyst can compare 2–10 companies against the same analysis profile to see a ranked comparison table.

**Independent Test**: Select AAPL, MSFT, GOOGL + "Value Investor" profile → see ranked comparison table.

### Implementation for User Story 5

- [ ] T600 [US5] Multi-company comparison — run same profile against 2–10 companies in `backend/app/services/analysis_service.py`
- [ ] T601 [US5] Comparison response format — ranked by overall score, per-criterion per-company in `backend/app/api/analysis.py`

### Tests for User Story 5

- [ ] T602 [P] [US5] Integration tests — comparison endpoint in `backend/tests/integration/test_comparison_api.py`

**Checkpoint**: At this point, all backend user stories should be independently functional

---

## Phase 8: User Story 6 - View & Export Financial Data (Priority: P3)

**Goal**: An analyst can view structured financial data in a table and export it to CSV.

**Independent Test**: View AAPL financials → see revenue, net income, etc. across years → export CSV.

> **Note**: Backend endpoints (T309, T310) were implemented in Phase 4 as part of US2. This story's remaining work is frontend only (covered in Phase 9).

**Checkpoint**: Backend complete from Phase 4. Frontend in Phase 9.

---

## Phase 9: User Story 7 - Full Web UI (Priority: P3)

**Goal**: A modern, responsive web interface with sidebar navigation, company management, document tracking, chat, analysis dashboards, and settings.

**Independent Test**: Navigate between dashboard, company detail (all tabs), analysis profiles, comparison, settings — all pages render correctly.

### Implementation for User Story 7

- [ ] T700 [US7] Next.js project setup — App Router, shadcn/ui, Tailwind CSS, React Query in `frontend/`
- [ ] T701 [US7] Layout — sidebar navigation, header, main content area in `frontend/src/app/layout.tsx`
- [ ] T702 [P] [US7] Dashboard page — company overview cards, quick actions, recent activity in `frontend/src/app/dashboard/page.tsx`
- [ ] T703 [P] [US7] Company list page — search, sort, filter, add company modal in `frontend/src/app/companies/page.tsx`
- [ ] T704 [US7] Company detail page — tab container (Overview, Documents, Financials, Chat, Analysis) in `frontend/src/app/companies/[id]/page.tsx`
- [ ] T705 [P] [US7] Documents tab — upload modal, SEC fetch modal, document table with status badges, timeline in `frontend/src/components/documents/`
- [ ] T706 [P] [US7] Financials tab — period selector, data table (metrics × years), metric charts, CSV export in `frontend/src/components/financials/`
- [ ] T707 [US7] Chat tab — session list, streaming chat interface, message bubbles, source panel, typing indicator in `frontend/src/components/chat/`
- [ ] T708 [US7] SSE client — parse event stream, render tokens incrementally, show sources on done in `frontend/src/lib/sse-client.ts`
- [ ] T709 [P] [US7] Analysis tab — profile selector, run button, score card, criteria table, trend charts, AI summary in `frontend/src/components/analysis/`
- [ ] T710 [P] [US7] Analysis profiles page — profile list, profile editor with criteria builder in `frontend/src/app/analysis/profiles/page.tsx`
- [ ] T711 [P] [US7] Comparison page — multi-company selector, comparison table, ranking chart in `frontend/src/app/analysis/compare/page.tsx`
- [ ] T712 [P] [US7] Settings page — LLM config, embedding config, ingestion config, API key status in `frontend/src/app/settings/page.tsx`
- [ ] T713 [US7] Responsive design (desktop-first, functional on tablet)
- [ ] T714 [US7] Loading states, error states, empty states for all pages in `frontend/src/components/ui/`
- [ ] T715 [P] [US7] Number formatting — `$394.3B`, `48.2%`, appropriate precision in `frontend/src/lib/format.ts`

### Tests for User Story 7

- [ ] T716 [P] [US7] Frontend component tests (Vitest + RTL) in `frontend/tests/`

**Checkpoint**: All user stories should now be independently functional with full UI

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T800 [P] Rate limiting implementation (100 req/min CRUD, 20 req/min chat) in `backend/app/api/middleware/`
- [ ] T801 E2E tests — company journey, upload+chat journey, analysis journey in `backend/tests/e2e/`
- [ ] T802 [P] Performance testing (Locust) — ingestion throughput, vector search latency, chat TTFT in `backend/tests/performance/`
- [ ] T803 Review & approve Docker image config — verify multi-stage builds, non-root user, image size < 200 MB for T804 + T805 (review gate, no code output)
- [ ] T804 [P] Backend Dockerfile (Python 3.12-slim, PyMuPDF deps, non-root) in `backend/Dockerfile`
- [ ] T805 [P] Frontend Dockerfile (Node 20-alpine, standalone build) in `frontend/Dockerfile`
- [ ] T806 CI/CD pipeline — GitHub Actions → build → test → push ACR → deploy Container Apps in `.github/workflows/`
- [ ] T807 [P] Azure Monitor alerts (API errors, ingestion stuck, LLM failures, DB issues, memory) in `infra/modules/`
- [ ] T808 [P] Azure Portal dashboards (API performance, ingestion pipeline, LLM usage, infra health) in `infra/dashboards/`
- [ ] T817 [P] Custom OpenTelemetry metric instrumentation — counters (ingestion_documents_total, chat_messages_total, analysis_runs_total, llm_api_calls_total, llm_tokens_total with labels type=prompt|completion and model), histograms (ingestion_duration_seconds, chat_retrieval_duration_seconds, chat_llm_duration_seconds, analysis_duration_seconds), gauges (companies_total, documents_total, vectors_total, celery_workers_active) in `backend/app/observability/metrics.py` (Constitution VII)
- [ ] T809 [P] README.md — local dev setup, architecture overview
- [ ] T810 [P] DEPLOYMENT.md — Azure deployment guide (Bicep, az CLI, secrets, verification)
- [ ] T812 Request validation hardening, error message review
- [ ] T813 [P] Log output review — no sensitive data, proper App Insights integration
- [ ] T814 [P] Dependency security audit
- [ ] T815 Circuit breaker implementation (Azure OpenAI, SEC EDGAR, Qdrant) in `backend/app/clients/`
- [ ] T819 [P] Qdrant unavailable degradation — CRUD and financial analysis remain functional, chat returns clear "unavailable" message in `backend/app/services/chat_service.py`
- [ ] T820 [P] No-XBRL-data handling — filings without XBRL data log warning, store available data, do not block text ingestion in `backend/app/ingestion/pipeline.py`
- [ ] T821 [P] Budget monitoring runbook — document manual scale-to-zero procedure, gpt-4o-mini switch, Redis removal steps for when $50/month dev budget is at risk in `docs/runbooks/budget-breach.md` (Constitution IV, spec edge case)
- [ ] T816 Run quickstart.md validation — all 6 scenarios pass
- [ ] T818 Ingestion idempotency verification — re-running full pipeline on already-ingested document produces identical chunks, vectors, and financial data (SC-012) in `backend/tests/integration/test_idempotency.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — 🎯 MVP starting point
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) — can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on US2 (needs embedded documents for RAG)
- **User Story 4 (Phase 6)**: Depends on US2 (needs financial data from XBRL extraction)
- **User Story 5 (Phase 7)**: Depends on US4 (needs analysis results to compare)
- **User Story 6 (Phase 8)**: Backend complete from US2; frontend in Phase 9
- **User Story 7 (Phase 9)**: Depends on all backend stories being complete (API-driven UI)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — No dependencies on other stories
- **US2 (P1)**: Can start after Foundational — No dependencies on other stories (can parallel with US1)
- **US3 (P1)**: Depends on US2 (needs embedded document chunks for RAG retrieval)
- **US4 (P2)**: Depends on US2 (needs extracted financial data for formula computation)
- **US5 (P3)**: Depends on US4 (needs analysis engine to run comparisons)
- **US6 (P3)**: Backend from US2; standalone for frontend
- **US7 (P3)**: Depends on all backend stories (API-driven frontend)

### Within Each User Story

- Models before services
- Services before API endpoints
- Core implementation before integration
- Tests after implementation (or TDD if preferred)
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- US1 and US2 can start in parallel after Foundational phase completes
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Frontend pages marked [P] can be developed in parallel
