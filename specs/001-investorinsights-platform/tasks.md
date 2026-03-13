# Tasks: InvestorInsights Platform

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [ ] `T-001` [P1] [Setup] Project scaffolding — monorepo with `backend/`, `frontend/`, `infra/`, `scripts/`
- [ ] `T-002` [P1] [Setup] Azure infrastructure provisioning via Bicep IaC (Resource Group, PostgreSQL B1ms, Blob Storage, Key Vault, ACR, Log Analytics, App Insights, OpenAI, Container Apps env)
- [ ] `T-003` [P1] [Setup] Bicep parameter files — `dev.bicepparam` (budget-optimised) and `prod.bicepparam` (full)
- [ ] `T-004` [P1] [Setup] Docker Compose for local development (PostgreSQL, Redis, Qdrant, Azurite)
- [ ] `T-005` [P1] [Setup] FastAPI application skeleton with Uvicorn, `app/main.py`, config loading
- [ ] `T-006` [P1] [Setup] Pydantic `BaseSettings` configuration validation (`app/config.py`)
- [ ] `T-007` [P1] [Setup] Structured logging setup — structlog + OpenTelemetry → Application Insights
- [ ] `T-008` [P1] [Setup] PostgreSQL schema + Alembic migration setup (`001_initial_schema.py`)
- [ ] `T-009` [P1] [Setup] SQLAlchemy ORM models for all entities (`app/models/`)
- [ ] `T-010` [P1] [Setup] Pydantic request/response schemas (`app/schemas/`)
- [ ] `T-011` [P1] [Setup] Azure Blob Storage client integration (`app/clients/storage_client.py`)
- [ ] `T-012` [P1] [Setup] Authentication middleware (API key from Key Vault, `X-API-Key` header)
- [ ] `T-013` [P1] [Setup] Error handling middleware (global exception handler, error taxonomy)
- [ ] `T-014` [P1] [Setup] Health check endpoint (`GET /api/v1/health` — ping DB, Redis, Qdrant, Blob)
- [ ] `T-015` [P1] [Setup] Makefile with common commands (setup, up, down, test, lint, migrate, azure-*)

---

## Phase 2: Foundational — Story 1 (Register & Browse Companies)

- [ ] `T-100` [P1] [Story 1] Company CRUD API — `POST/GET/PUT/DELETE /api/v1/companies`
- [ ] `T-101` [P1] [Story 1] SEC EDGAR client — ticker → CIK resolution, company metadata lookup
- [ ] `T-102` [P1] [Story 1] Company repository (data access layer)
- [ ] `T-103` [P1] [Story 1] Company service (business logic, auto-resolve from SEC)
- [ ] `T-104` [P1] [Story 1] Unique ticker constraint enforcement (409 on duplicate)
- [ ] `T-105` [P1] [Story 1] Company list with summary statistics (doc count, latest filing, readiness %)
- [ ] `T-106` [P1] [Story 1] Company delete with CASCADE cleanup (all associated data)
- [ ] `T-107` [P1] [Story 1] Unit tests — company service, SEC client (mocked)
- [ ] `T-108` [P1] [Story 1] Integration tests — company CRUD API against test DB

---

## Phase 3: Story 2 — Upload & Ingest SEC Filings

- [ ] `T-200` [P1] [Story 2] Document upload API — `POST /companies/{id}/documents` (multipart)
- [ ] `T-201` [P1] [Story 2] File storage in Azure Blob Storage (organised by company/type/year)
- [ ] `T-202` [P1] [Story 2] Document status state machine (uploaded → parsing → parsed → embedding → ready → error)
- [ ] `T-203` [P1] [Story 2] Celery worker setup with Redis broker, ingestion/analysis/sec_fetch queues
- [ ] `T-204` [P1] [Story 2] PDF text extraction — PyMuPDF parser
- [ ] `T-205` [P1] [Story 2] HTML text extraction — BeautifulSoup + custom cleaner
- [ ] `T-206` [P1] [Story 2] Text cleaning and normalisation (Unicode, whitespace, headers/footers, tables → markdown)
- [ ] `T-207` [P1] [Story 2] Section splitter — regex-based for 10-K Items (1, 1A, 1B, 1C, 2, 3, 5, 7, 7A, 8, 9A) and 10-Q
- [ ] `T-208` [P1] [Story 2] Text chunker — recursive character splitter (768 tokens, 128 overlap, tiktoken)
- [ ] `T-209` [P1] [Story 2] Qdrant collection management — create per-company collection (3072 dims, cosine)
- [ ] `T-210` [P1] [Story 2] Azure OpenAI embedding integration — batch embed chunks (text-embedding-3-large)
- [ ] `T-211` [P1] [Story 2] Vector upsert to Qdrant with metadata payload
- [ ] `T-212` [P1] [Story 2] Ingestion pipeline orchestrator — coordinates all stages, updates status
- [ ] `T-213` [P1] [Story 2] Duplicate upload prevention (409 for same company + type + year + quarter)
- [ ] `T-214` [P1] [Story 2] Document retry API — `POST /documents/{id}/retry` (re-run from failed stage)
- [ ] `T-215` [P1] [Story 2] Document delete with cascade — remove file, vectors, sections, chunks, financials
- [ ] `T-216` [P1] [Story 2] Corrupt file handling — graceful error with clear message
- [ ] `T-217` [P1] [Story 2] Unit tests — parser, splitter, chunker, cleaner
- [ ] `T-218` [P1] [Story 2] Integration tests — full pipeline (upload → ready)

---

## Phase 4: Story 2 (continued) — SEC EDGAR Integration

- [ ] `T-300` [P1] [Story 2] SEC EDGAR filing index fetcher — list available filings for company/CIK
- [ ] `T-301` [P1] [Story 2] SEC EDGAR filing downloader — fetch actual filing documents
- [ ] `T-302` [P1] [Story 2] Rate limiter for SEC API (max 10 req/s, User-Agent header)
- [ ] `T-303` [P1] [Story 2] XBRL `companyfacts` API integration — fetch structured financial data
- [ ] `T-304` [P1] [Story 2] XBRL tag → internal schema mapper (60+ US-GAAP tags)
- [ ] `T-305` [P1] [Story 2] Financial statements storage in PostgreSQL (JSONB `statement_data`)
- [ ] `T-306` [P1] [Story 2] Auto-fetch API — `POST /companies/{id}/documents/fetch-sec`
- [ ] `T-307` [P1] [Story 2] Celery queue for SEC fetch tasks (skip duplicates, progress tracking)
- [ ] `T-308` [P1] [Story 2] Async task status API — `GET /tasks/{task_id}`
- [ ] `T-309` [P1] [Story 2] Financial data API — `GET /companies/{id}/financials`
- [ ] `T-310` [P1] [Story 2] CSV export — `GET /companies/{id}/financials/export`
- [ ] `T-311` [P1] [Story 2] Unit tests — XBRL mapper, SEC client, period selection
- [ ] `T-312` [P1] [Story 2] Integration tests — fetch + extract flow

---

## Phase 5: Story 3 — Chat with AI About Company Filings

- [ ] `T-400` [P1] [Story 3] Chat session management — create, list, get, delete
- [ ] `T-401` [P1] [Story 3] Chat message persistence (role, content, sources, token_count)
- [ ] `T-402` [P1] [Story 3] Vector similarity search — query embedding + Qdrant search with metadata filters
- [ ] `T-403` [P1] [Story 3] System prompt builder — company-specific prompt with rules
- [ ] `T-404` [P1] [Story 3] Context assembly — retrieved chunks + conversation history within token budget
- [ ] `T-405` [P1] [Story 3] Azure OpenAI chat completion with streaming (SSE, with direct OpenAI fallback)
- [ ] `T-406` [P1] [Story 3] SSE endpoint — `POST /companies/{id}/chat` with event types: session, sources, token, done, error
- [ ] `T-407` [P1] [Story 3] Source citation extraction and formatting
- [ ] `T-408` [P1] [Story 3] Conversation history management (last N exchanges, configurable, token budget)
- [ ] `T-409` [P1] [Story 3] Session title auto-generation (from first user message)
- [ ] `T-410` [P1] [Story 3] Retrieval config support (top_k, score_threshold, doc_type/year/section filters)
- [ ] `T-411` [P1] [Story 3] No-results handling — inform user, suggest rephrasing
- [ ] `T-412` [P1] [Story 3] Out-of-scope refusal (predictions, buy/sell, unrelated topics)
- [ ] `T-413` [P1] [Story 3] Unit tests — prompt builder, retrieval logic, context assembly
- [ ] `T-414` [P1] [Story 3] Integration tests — full chat flow (mocked LLM)

---

## Phase 6: Story 4 — Score Companies with Analysis Profiles

- [ ] `T-500` [P2] [Story 4] Formula registry — 25+ built-in formulas (profitability, growth, liquidity, solvency, efficiency, cash flow, dividend)
- [ ] `T-501` [P2] [Story 4] Custom formula expression parser (lexer + recursive descent parser + evaluator)
- [ ] `T-502` [P2] [Story 4] `prev()` reference resolution — previous period data lookback
- [ ] `T-503` [P2] [Story 4] Formula validation at save time (field references, balanced parens, syntax)
- [ ] `T-504` [P2] [Story 4] Analysis profile CRUD API — `POST/GET/PUT/DELETE /analysis/profiles`
- [ ] `T-505` [P2] [Story 4] Analysis criteria management (1–30 per profile, with category, formula, comparison, threshold, weight, lookback)
- [ ] `T-506` [P2] [Story 4] Analysis execution engine — load financials, compute formulas across years, evaluate thresholds
- [ ] `T-507` [P2] [Story 4] Trend detection — OLS linear regression (improving/declining/stable, min 3 data points)
- [ ] `T-508` [P2] [Story 4] Scoring — binary pass/fail × weight, null handling (no_data excluded from max), grade A–F
- [ ] `T-509` [P2] [Story 4] Analysis run API — `POST /analysis/run` (1–10 companies × 1 profile)
- [ ] `T-510` [P2] [Story 4] Analysis results persistence (JSONB result_details, overall/max/pct scores)
- [ ] `T-511` [P2] [Story 4] AI narrative summary generation via LLM (strengths, concerns, data gaps)
- [ ] `T-512` [P2] [Story 4] Analysis results API — `GET /analysis/results`, `GET /analysis/results/{id}`
- [ ] `T-513` [P2] [Story 4] Built-in formulas list API — `GET /analysis/formulas`
- [ ] `T-514` [P2] [Story 4] Default analysis profile seeding (Quality Value Investor, 15 criteria)
- [ ] `T-515` [P2] [Story 4] Unit tests — all 25+ formulas, parser, scorer, trend detection, threshold evaluator
- [ ] `T-516` [P2] [Story 4] Integration tests — full analysis flow

---

## Phase 7: Story 5 — Compare Companies

- [ ] `T-600` [P3] [Story 5] Multi-company comparison — run same profile against 2–10 companies
- [ ] `T-601` [P3] [Story 5] Comparison response format — ranked by overall score, per-criterion per-company
- [ ] `T-602` [P3] [Story 5] Integration tests — comparison endpoint

---

## Phase 8: Story 7 — Frontend Application

- [ ] `T-700` [P3] [Story 7] Next.js project setup — App Router, shadcn/ui, Tailwind CSS, React Query
- [ ] `T-701` [P3] [Story 7] Layout — sidebar navigation, header, main content area
- [ ] `T-702` [P3] [Story 7] Dashboard page — company overview cards, quick actions, recent activity
- [ ] `T-703` [P3] [Story 7] Company list page — search, sort, filter, add company modal
- [ ] `T-704` [P3] [Story 7] Company detail page — tab container (Overview, Documents, Financials, Chat, Analysis)
- [ ] `T-705` [P3] [Story 7] Documents tab — upload modal, SEC fetch modal, document table with status badges, timeline
- [ ] `T-706` [P3] [Story 7] Financials tab — period selector, data table (metrics × years), metric charts, CSV export
- [ ] `T-707` [P3] [Story 7] Chat tab — session list, streaming chat interface, message bubbles, source panel, typing indicator
- [ ] `T-708` [P3] [Story 7] SSE client — parse event stream, render tokens incrementally, show sources on done
- [ ] `T-709` [P3] [Story 7] Analysis tab — profile selector, run button, score card, criteria table, trend charts, AI summary
- [ ] `T-710` [P3] [Story 7] Analysis profiles page — profile list, profile editor with criteria builder
- [ ] `T-711` [P3] [Story 7] Comparison page — multi-company selector, comparison table, ranking chart
- [ ] `T-712` [P3] [Story 7] Settings page — LLM config, embedding config, ingestion config, API key status
- [ ] `T-713` [P3] [Story 7] Responsive design (desktop-first, functional on tablet)
- [ ] `T-714` [P3] [Story 7] Loading states, error states, empty states for all pages
- [ ] `T-715` [P3] [Story 7] Number formatting — `$394.3B`, `48.2%`, appropriate precision
- [ ] `T-716` [P3] [Story 7] Frontend component tests (Vitest + RTL)

---

## Phase 9: Polish & Production Readiness

- [ ] `T-800` [P1] [Polish] Rate limiting implementation (100 req/min CRUD, 20 req/min chat)
- [ ] `T-801` [P1] [Polish] E2E tests — company journey, upload+chat journey, analysis journey
- [ ] `T-802` [P1] [Polish] Performance testing (Locust) — ingestion throughput, vector search latency, chat TTFT
- [ ] `T-803` [P1] [Polish] Production Docker images — multi-stage, non-root user
- [ ] `T-804` [P1] [Polish] Backend Dockerfile (Python 3.12-slim, PyMuPDF deps, non-root)
- [ ] `T-805` [P1] [Polish] Frontend Dockerfile (Node 20-alpine, standalone build)
- [ ] `T-806` [P1] [Polish] CI/CD pipeline — GitHub Actions → build → test → push ACR → deploy Container Apps
- [ ] `T-807` [P1] [Polish] Azure Monitor alerts (API errors, ingestion stuck, LLM failures, DB issues, memory)
- [ ] `T-808` [P1] [Polish] Azure Portal dashboards (API performance, ingestion pipeline, LLM usage, infra health)
- [ ] `T-809` [P1] [Polish] README.md — local dev setup, architecture overview
- [ ] `T-810` [P1] [Polish] DEPLOYMENT.md — Azure deployment guide (Bicep, az CLI, secrets, verification)
- [ ] `T-811` [P1] [Polish] Default analysis profile seed script
- [ ] `T-812` [P1] [Polish] Request validation hardening, error message review
- [ ] `T-813` [P1] [Polish] Log output review — no sensitive data, proper App Insights integration
- [ ] `T-814` [P1] [Polish] Dependency security audit
- [ ] `T-815` [P1] [Polish] Circuit breaker implementation (Azure OpenAI, SEC EDGAR, Qdrant)
