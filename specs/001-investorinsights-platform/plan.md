# Implementation Plan: InvestorInsights Platform

**Branch**: `001-investorinsights-platform` | **Date**: 2025-01-XX | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-investorinsights-platform/spec.md`
**Status**: Draft

---

## Summary

Build an Azure cloud-deployed platform for analysing public company SEC filings. The
system has three core capabilities: (1) document ingestion pipeline that parses, chunks,
embeds, and extracts XBRL financial data from SEC filings; (2) a per-company RAG chat
agent that answers qualitative questions grounded in filing text; (3) a configurable
financial analysis engine that scores companies against user-defined criteria. The
frontend is a Next.js web app with real-time chat streaming, data tables, and charts.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.4+ (frontend)
**Primary Dependencies**: FastAPI 0.110+, SQLAlchemy 2.0+, Celery 5.3+, Next.js 14+, shadcn/ui
**Storage**: Azure DB for PostgreSQL Flex (relational), Qdrant (vectors), Azure Blob Storage (files), Redis (cache/broker)
**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
**Target Platform**: Microsoft Azure Cloud (Container Apps, managed services)
**Project Type**: web-service (API + async worker + frontend)
**Performance Goals**: <500ms p95 API, <2s chat TTFT, <5min 10-K ingestion, <3s analysis (30 criteria × 10 years)
**Constraints**: Dev environment ≤ $50/month (~$22–34 estimated), SEC EDGAR 10 req/s, single-user V1
**Scale/Scope**: 100 companies, 5,000 documents, 500K+ vectors, 7 user stories, ~15 pages frontend

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How This Plan Aligns |
|-----------|---------------------|
| Company-Scoped | All data models are keyed by `company_id`; vector collections are per-company |
| Grounded AI | System prompt enforces citation-only answers; no external knowledge |
| User-Defined Criteria | Analysis profiles are fully user-configurable; 25+ built-in formulas + custom DSL |
| Azure Cloud-Native | All infrastructure via Bicep IaC; managed PostgreSQL, Blob Storage, OpenAI, Key Vault |
| Single User (V1) | API key auth; no multi-tenant complexity |
| Offline-Capable | Raw files in Blob Storage; analysis works without re-fetching SEC |
| Observability | structlog + OpenTelemetry → Application Insights; custom metrics for all pipelines |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-investorinsights-platform/
├── spec.md              # Feature specification (user stories, requirements, success criteria)
├── plan.md              # This file — architecture, tech stack, infrastructure, data flows
├── research.md          # Key technical decisions with rationale
├── data-model.md        # ERD, entities, enums, JSONB schemas, Qdrant config
├── quickstart.md        # 6 validation scenarios with curl commands
├── tasks.md             # 10-phase task breakdown (T001 → T821)
├── contracts/
│   └── api-spec.md      # Full REST API contract
├── checklists/
│   └── requirements.md  # FR/NFR/SC checkbox tracker
└── reference/           # 9 reference files (formulas, XBRL mapping, DDL, etc.)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── api/             # FastAPI route handlers
│   ├── services/        # Business logic layer
│   ├── clients/         # External service clients (SEC, OpenAI, Qdrant, Blob)
│   ├── ingestion/       # Pipeline stages (parse, split, chunk, embed, extract)
│   ├── analysis/        # Formula engine, expression parser, scoring
│   └── worker/          # Celery app, task definitions
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── requirements.txt
└── Dockerfile

frontend/
├── src/
│   ├── app/             # Next.js App Router pages
│   ├── components/      # React components (shadcn/ui based)
│   ├── lib/             # API client, utilities
│   └── types/           # TypeScript types
├── tests/
├── package.json
└── Dockerfile

infra/
├── main.bicep
├── parameters/          # dev.bicepparam, prod.bicepparam
├── modules/             # Bicep modules (12 modules)
├── dashboards/          # Azure Monitor dashboard JSON templates
└── scripts/             # deploy.sh, destroy.sh, seed-keyvault.sh
```

**Structure Decision**: Web application pattern (frontend + backend + infra). Monorepo with three top-level directories. See [`reference/project-structure.md`](reference/project-structure.md) for the complete directory tree.

---

## System Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│    ┌────────────────────────────────────────────────────────────────────┐     │
│    │                    Next.js Web Application                        │     │
│    │                  (Azure Container Apps)                           │     │
│    │  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌────────────┐   │     │
│    │  │ Company  │  │  Document    │  │   Chat    │  │  Analysis  │   │     │
│    │  │ Manager  │  │  Manager     │  │ Interface │  │ Dashboard  │   │     │
│    │  └──────────┘  └──────────────┘  └───────────┘  └────────────┘   │     │
│    └───────────────────────────┬────────────────────────────────────────┘     │
│                                │  HTTP/SSE                                    │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                 API LAYER (FastAPI — Azure Container Apps)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────────┐      │
│  │  /companies │  │  /documents  │  │  /chat   │  │  /analysis         │      │
│  │  CRUD       │  │  upload,     │  │  SSE     │  │  profiles, run,    │      │
│  │             │  │  status,     │  │  stream  │  │  results, compare  │      │
│  │             │  │  fetch-sec   │  │          │  │                    │      │
│  └──────┬──────┘  └──────┬───────┘  └────┬─────┘  └─────────┬──────────┘      │
│         │                │               │                   │                 │
│  ┌──────┴────────────────┴───────────────┴───────────────────┴──────────────┐  │
│  │                        SERVICE LAYER                                     │  │
│  │  CompanyService │ DocumentService │ ChatService/Agent │ AnalysisEngine   │  │
│  │  IngestionPipeline (parse → split → extract XBRL → chunk → embed)       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└───────────────┬──────────────┬───────────────┬──────────────┬─────────────────┘
                │              │               │              │
                ▼              ▼               ▼              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Azure Managed Services)                       │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Azure DB for │  │ Qdrant        │  │ Azure Blob   │  │ Redis            │  │
│  │ PostgreSQL   │  │ (Container    │  │ Storage      │  │ (Container App   │  │
│  │ Flex Server  │  │  Apps)        │  │              │  │  dev / Azure     │  │
│  │              │  │               │  │              │  │  Cache prod)     │  │
│  └──────────────┘  └───────────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
         │                                           │
         ▼                                           ▼
┌─────────────────────────────┐   ┌──────────────────────────────────────────┐
│    EXTERNAL SERVICES        │   │    ASYNC WORKER (Azure Container Apps)   │
│  • SEC EDGAR API            │   │  Celery Workers (1–10)                   │
│  • Azure OpenAI Service     │   │  Queues: ingestion, analysis, sec_fetch  │
│  • Azure Key Vault          │   │                                          │
│  • Azure Monitor            │   │                                          │
└─────────────────────────────┘   └──────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Statefulness |
|-----------|---------------|-------------|
| FastAPI App | HTTP handling, validation, routing, SSE streaming, auth | Stateless |
| CompanyService | Company CRUD, CIK resolution from SEC EDGAR | Stateless |
| DocumentService | File upload to Blob Storage, metadata CRUD, trigger ingestion | Stateless |
| IngestionPipeline | Parse → split sections → chunk → embed → extract XBRL | Stateless (all state in DB) |
| ChatService / CompanyChatAgent | RAG retrieval, prompt construction, LLM streaming | Stateless per request |
| FinancialAnalysisEngine | Formula computation, threshold evaluation, trend detection, scoring | Stateless |
| Celery Workers | Async task execution for ingestion and analysis | Stateless (pull from queue) |
| Azure DB for PostgreSQL | Relational data (companies, documents, financials, profiles, results, chats) | Persistent (managed) |
| Qdrant (Container Apps) | Vector storage and similarity search, per-company collections | Persistent (volume-mounted) |
| Azure Blob Storage | Raw file storage (PDFs, HTMLs, exports) | Persistent (managed) |
| Redis | Celery broker, caching, rate limiting | Semi-persistent (loss is recoverable) |

---

## Technology Stack

### Backend

| Component | Technology | Version | Justification |
|-----------|-----------|---------|--------------|
| Language | Python | 3.12+ | Rich ML/AI ecosystem, async support |
| API Framework | FastAPI | 0.110+ | Async, auto-docs, Pydantic validation, SSE |
| ASGI Server | Uvicorn | 0.29+ | Production-grade ASGI server |
| ORM | SQLAlchemy | 2.0+ | Async support, type-safe queries |
| Migrations | Alembic | 1.13+ | Versioned migrations |
| Task Queue | Celery | 5.3+ | Mature async task processing |
| HTTP Client | httpx | 0.27+ | Async HTTP for SEC API, LLM calls |
| PDF Parser | PyMuPDF (fitz) | 1.24+ | Fast, reliable PDF text extraction |
| HTML Parser | BeautifulSoup4 | 4.12+ | Standard HTML parsing |
| Tokenizer | tiktoken | 0.7+ | OpenAI tokenizer for chunk sizing |
| LLM Client | openai SDK | 1.30+ | Supports Azure OpenAI + direct OpenAI |
| Vector Client | qdrant-client | 1.9+ | Official async SDK |
| Blob Client | azure-storage-blob | 12.20+ | Azure Blob Storage SDK |
| Azure Identity | azure-identity | 1.16+ | Managed Identity auth |
| Validation | Pydantic | 2.7+ | Data validation, serialization |
| Linting | Ruff | 0.4+ | Fast linter/formatter |
| Type Checking | mypy | 1.10+ | Static type checking |
| Testing | pytest + pytest-asyncio | 8.0+ | Standard Python testing |

### Frontend

| Component | Technology | Version | Justification |
|-----------|-----------|---------|--------------|
| Framework | Next.js | 14+ | React SSR, App Router |
| Language | TypeScript | 5.4+ | Type safety |
| UI Library | shadcn/ui | latest | High-quality, customizable components |
| Styling | Tailwind CSS | 3.4+ | Utility-first CSS |
| Charts | Recharts | 2.12+ | React-native charting |
| State | React Query (TanStack) | 5+ | Server state management |
| Forms | React Hook Form + Zod | latest | Form validation |
| Markdown | react-markdown | 9+ | Render LLM responses |
| SSE | eventsource-parser | latest | Parse SSE streams |
| Testing | Vitest + React Testing Library | latest | Component testing |

### Data Infrastructure

| Component | Technology | Dev SKU | Prod SKU |
|-----------|-----------|---------|----------|
| Relational DB | Azure DB for PostgreSQL Flex | Burstable B1ms (1 vCore, 2 GB) | General Purpose D2ds_v5 (2 vCore, 8 GB) |
| Vector DB | Qdrant on Container Apps | 0.25 CPU, 1 GB RAM, scale-to-zero | 1.0 CPU, 4 GB RAM |
| Object Storage | Azure Blob Storage | Standard LRS | Standard ZRS |
| Cache/Broker | Redis container (dev) / Azure Cache for Redis (prod) | Container App, scale-to-zero | Standard C1 (1 GB) |

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Azure OpenAI | Embeddings (text-embedding-3-large) + Chat (gpt-4o-mini dev / gpt-4o prod) | Yes (primary) |
| OpenAI API (direct) | Fallback LLM/embedding provider | No (optional) |
| SEC EDGAR API | Company info, filing index, XBRL data | Yes (free) |
| Azure Key Vault | Secrets management | Yes |
| Azure Monitor / App Insights | Logging, metrics, tracing, alerting | Yes |
| Azure Container Registry | Docker image storage | Yes |

---

## Infrastructure & Deployment

### Azure Resource Layout

```text
Azure Resource Group: rg-investorinsights-{env}
├── Container Apps Environment (Consumption plan)
│   ├── api        (FastAPI)        dev: 0→1  / prod: 1→5
│   ├── worker     (Celery)         dev: 0→2  / prod: 1→5
│   ├── frontend   (Next.js)        dev: 0→1  / prod: 1→3
│   ├── qdrant     (vector DB)      dev: 0→1  / prod: 1
│   └── redis      (dev only)       dev: 0→1
├── Azure DB for PostgreSQL Flex    dev: B1ms / prod: D2ds_v5
├── Azure Blob Storage              dev: LRS  / prod: ZRS
├── Azure Cache for Redis           prod only (Standard C1)
├── Azure OpenAI Service            dev: gpt-4o-mini / prod: gpt-4o
├── Azure Key Vault
├── Azure Container Registry        dev: Basic / prod: Standard
├── Log Analytics + App Insights
└── VNet + Private Endpoints        prod only
```

### Dev Cost Breakdown (≤ $50/month target)

| Resource | Estimated Monthly Cost |
|----------|----------------------|
| PostgreSQL Burstable B1ms | ~$13.00 |
| Azure Blob Storage (LRS, <1 GB) | ~$0.50 |
| Container Apps (Consumption, scale-to-zero) | ~$3–10 |
| Azure Container Registry (Basic) | ~$5.00 |
| Azure Key Vault (low ops) | ~$0.03 |
| Log Analytics (~0.5 GB/mo) | ~$0.00 (free tier) |
| Azure OpenAI (gpt-4o-mini + embeddings) | ~$1–5 |
| Redis container (in Container Apps) | ~$0.00 |
| **TOTAL** | **~$22–34/month** |

### Networking

- **Dev**: Public endpoints + IP-based firewall rules (no VNet — saves ~$40/mo)
- **Prod**: Full VNet (10.0.0.0/16) with private endpoints for all data services

### Infrastructure as Code (Bicep)

```
infra/
├── main.bicep                   # Orchestrator
├── parameters/
│   ├── dev.bicepparam           # Budget-optimised
│   └── prod.bicepparam          # Full production
├── modules/
│   ├── resource-group.bicep
│   ├── networking.bicep         # VNet + private endpoints (prod only)
│   ├── postgresql.bicep
│   ├── redis.bicep              # Azure Cache for Redis (prod only)
│   ├── storage.bicep            # Blob Storage + containers
│   ├── openai.bicep             # Azure OpenAI + model deployments
│   ├── key-vault.bicep
│   ├── container-registry.bicep
│   ├── log-analytics.bicep
│   ├── app-insights.bicep
│   └── container-apps.bicep     # Environment + all apps (incl. redis in dev)
├── dashboards/
│   ├── api-performance.json
│   ├── ingestion-pipeline.json
│   ├── llm-usage.json
│   └── infra-health.json
└── scripts/
    ├── deploy.sh
    ├── destroy.sh
    └── seed-keyvault.sh
```

### Secrets Management (Azure Key Vault)

Container Apps access secrets via system-assigned managed identity. No plaintext secrets in IaC or config.

| Secret | Description |
|--------|-------------|
| `db-connection-string` | Azure PostgreSQL connection string |
| `redis-connection-string` | Redis connection (prod: Azure Cache) |
| `blob-storage-connection` | Azure Blob Storage connection string |
| `azure-openai-api-key` | Azure OpenAI key |
| `azure-openai-endpoint` | Azure OpenAI endpoint URL |
| `api-auth-key` | Application API key for V1 auth |
| `sec-edgar-user-agent` | SEC EDGAR User-Agent header value |

### Backup Strategy

| Store | Method | Dev Retention | Prod Retention |
|-------|--------|--------------|----------------|
| PostgreSQL | Azure-managed automated (PITR) | 7 days | 35 days (geo-redundant) |
| Blob Storage | Soft delete + versioning | N/A | 14 days |
| Qdrant | Snapshot API → Azure Files | 14 days | 14 days |
| Redis | N/A (transient, loss is recoverable) | — | — |

---

## Ingestion Pipeline Detail

```text
Stage 1: PARSE       Stage 2: SPLIT         Stage 3: EXTRACT     Stage 4: EMBED
┌──────────┐        ┌──────────────┐        ┌──────────────┐     ┌──────────────┐
│ PDF→text │───────▶│ Section      │───────▶│ XBRL         │────▶│ Chunk text   │
│ HTML→text│        │ Splitter     │        │ Financial    │     │ Embed chunks │
│          │        │ (Items 1–15) │        │ Extraction   │     │ Store vectors│
└──────────┘        └──────────────┘        └──────────────┘     └──────────────┘
Status: uploaded     Status: parsing         (parallel with       Status: embedding
       →parsing             →parsed          stage 4)                    →ready
```

### Document Parsing

| Format | Parser | Notes |
|--------|--------|-------|
| PDF | PyMuPDF (fitz) | Page-by-page extraction, handle multi-column |
| HTML | BeautifulSoup + custom cleaner | Strip tags, preserve tables as markdown |

**Cleaning rules**: Remove headers/footers, normalise Unicode, collapse blank lines, remove TOC pages, preserve table data as pipe-delimited markdown, remove image references.

### Section Splitting

Pattern-based regex matching for 10-K Items (1, 1A, 1B, 1C, 2, 3, 5, 6, 7, 7A, 8, 9A). Disambiguation: take LAST occurrence of section header (skip TOC duplicates). See `reference/sec-filing-sections.md` for full patterns.

### Chunking

```yaml
method: recursive_character_text_splitter
chunk_size: 768 tokens
chunk_overlap: 128 tokens
tokenizer: tiktoken (cl100k_base)
separators: ["\n\n\n", "\n\n", "\n", ". ", " "]
```

### Financial Data Extraction

**Source**: SEC EDGAR XBRL `companyfacts` API (`https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`). Single API call returns all historical XBRL data. Maps 60+ US-GAAP tags to internal schema. See `reference/xbrl-tag-mapping.md`.

### Embedding

```yaml
provider: azure_openai
model: text-embedding-3-large
dimensions: 3072  # full dimensionality, no reduction via API dimensions parameter
batch_size: 64
rate_limit: 3000 requests/minute
```

---

## RAG Chat Agent Detail

### System Prompt

Company-specific prompt injecting company name, ticker, CIK, filing date range, available document types. Rules enforce: ground in provided excerpts, cite sources, be precise with numbers, compare across periods, distinguish facts from analysis, refuse out-of-scope requests, handle ambiguity.

### Retrieval

```yaml
default_top_k: 15
max_top_k: 50
score_threshold: 0.65 (cosine similarity)
query_expansion: LLM-based (generate 2–3 alternative queries, controllable via config toggle)
context_budget: 12000 tokens max
history_budget: 4000 tokens max (spec FR-405: default 10 exchanges, 4000 token budget)
response_budget: 4096 tokens max
```

### Prompt Construction

```
[0] system: {company-specific system prompt}
[1..N-1] user/assistant: {conversation history, last 10 exchanges}
[N] user: {retrieved filing excerpts with source labels} + {user question}
```

### LLM Configuration

```yaml
provider: azure_openai
deployment: gpt-4o-mini (dev) / gpt-4o (prod)
temperature: 0.2
max_tokens: 4096
streaming: true
timeout: 120s
```

---

## Financial Analysis Engine Detail

### Built-in Formulas

25+ formulas across categories: Profitability (gross_margin, operating_margin, net_margin, roe, roa, roic), Growth (revenue_growth, earnings_growth, fcf_growth), Liquidity (current_ratio, quick_ratio, cash_ratio), Solvency (debt_to_equity, interest_coverage), Efficiency (asset_turnover, inventory_turnover), Cash Flow Quality (fcf_margin, operating_cash_flow_ratio), Dividend (payout_ratio). See `reference/builtin-formulas.md`.

### Custom Formula DSL

Expression syntax: field references (`income_statement.revenue`), operators (`+ - * / ^`), functions (`abs`, `min`, `max`, `avg`), previous period (`prev(field, lookback)`). Parser validates at save time.

### Trend Detection

OLS linear regression over available years (minimum 3 non-null values). Normalised slope = OLS slope / mean of non-null values. Normalised slope > +3% → improving, < -3% → declining, otherwise → stable.

### Scoring

Binary pass/fail per criterion × weight. `no_data` criteria excluded from max. Grade: A (90–100%), B (75–89%), C (60–74%), D (40–59%), F (0–39%).

---

## Security

### Authentication (V1)

API key in `X-API-Key` header, stored in Azure Key Vault, injected via managed identity. Constant-time comparison. All endpoints except `/health` require auth. V2 path: Azure AD / Entra ID.

### Input Validation

- File uploads: 50 MB max, magic bytes validation, filename sanitisation
- Text: chat 10K chars, formulas 500 chars
- Numeric: fiscal_year 1990–2100, quarter 1–4, weight > 0
- SQL injection: SQLAlchemy parameterised queries
- XSS: React auto-escape, markdown allowlist

### LLM Prompt Security

User input placed only in user content section, never in system prompt. System prompt hardcoded server-side. Retrieved context delimited from user input. No tool-use / function-calling.

---

## Error Handling & Resilience

### Retry Policies

| Service | Max Retries | Backoff | Retry On |
|---------|------------|---------|----------|
| Azure OpenAI | 3 | Exponential (1s, 2s, 4s) | 429, 500, 502, 503, timeout |
| SEC EDGAR | 5 | Exponential (2s → 32s) | 429, 500, 502, 503, connection |
| Qdrant | 3 | Exponential (0.5s, 1s, 2s) | Connection, timeout |
| Celery tasks | 3 | Exponential (60s, 300s, 900s) | Any transient failure |

### Circuit Breakers

| Service | Failure Threshold | Recovery Timeout | Fallback |
|---------|------------------|-----------------|----------|
| Azure OpenAI | 5 consecutive | 60s | Direct OpenAI (if configured) |
| SEC EDGAR | 10 consecutive | 300s | Queue for later; existing docs unaffected |
| Qdrant | 3 consecutive | 30s | Chat unavailable; CRUD still works |

---

## Observability

### Logging

structlog with JSON output → OpenTelemetry → Application Insights. Standard fields: timestamp, level, message, service, request_id, company_id, document_id, duration_ms. Sensitive data redacted.

### Metrics (OpenTelemetry → Application Insights)

**Counters**: ingestion_documents_total, chat_messages_total, analysis_runs_total, llm_api_calls_total, llm_tokens_total (labels: type=prompt|completion, model)
**Histograms**: ingestion_duration_seconds, chat_retrieval_duration_seconds, chat_llm_duration_seconds, analysis_duration_seconds
**Gauges**: companies_total, documents_total, vectors_total, celery_workers_active

### Alerting (Azure Monitor)

- High API error rate (>10% over 5 min) → Severity 2
- Ingestion pipeline stuck (>5 errors/hour) → Severity 2
- LLM API failures (>5 in 5 min) → Severity 1
- Database connection issues (>3 in 5 min) → Severity 1

### Dashboards (Azure Portal JSON templates)

API Performance, Ingestion Pipeline, LLM & AI Usage, Infrastructure Health.

---

## Configuration Management

12-factor app: all config via environment variables. Local dev: `.env` file with Docker Compose. Azure: secrets from Key Vault (managed identity references), non-secrets as Container App env vars.

Pydantic `BaseSettings` validates all config at startup. Missing required vars → startup failure with clear message. Connectivity checks for DB, Redis, Qdrant, Blob Storage on boot.

See `reference/env-config.md` for the complete environment variable reference.

---

## Data Flow Diagrams

### Document Upload & Ingestion Flow

```text
User                  API                   Worker              Blob    Postgres    Qdrant
  │                    │                      │                  │         │          │
  │── POST /documents ─▶│                     │                  │         │          │
  │   (file + metadata) │                     │                  │         │          │
  │                    │── store file ────────────────────────────▶│        │          │
  │                    │── create doc record ─────────────────────────────▶│          │
  │                    │   (status=uploaded)   │                  │         │          │
  │                    │── enqueue task ──────▶│                  │         │          │
  │◀── 202 Accepted ──│                      │                  │         │          │
  │   (document_id)    │                      │                  │         │          │
  │                    │                      │── fetch file ────▶│        │          │
  │                    │                      │◀── file content ──│        │          │
  │                    │                      │── update status (parsing) ▶│          │
  │                    │                      │── parse PDF/HTML  │         │          │
  │                    │                      │── split sections  │         │          │
  │                    │                      │── save sections ──────────▶│          │
  │                    │                      │── extract XBRL ──┼── SEC API         │
  │                    │                      │── save financials ────────▶│          │
  │                    │                      │── update status (embedding)▶│         │
  │                    │                      │── chunk text      │         │          │
  │                    │                      │── generate embeddings (Azure OpenAI)  │
  │                    │                      │── upsert vectors ─────────────────────▶│
  │                    │                      │── save chunk records ─────▶│          │
  │                    │                      │── update status (ready) ──▶│          │
```

### Chat Flow

```text
User                  API                   ChatAgent          Qdrant  AzureOpenAI  Postgres
  │                    │                      │                  │         │          │
  │── POST /chat ─────▶│                     │                  │         │          │
  │   (message, session)│                     │                  │         │          │
  │                    │── load company info ─────────────────────────────────────────▶│
  │                    │── load chat history ─────────────────────────────────────────▶│
  │                    │── create agent ─────▶│                  │         │          │
  │                    │                      │── embed query ───────────▶│          │
  │                    │                      │◀── query vector ──────────│          │
  │                    │                      │── search ────────▶│        │          │
  │                    │                      │◀── top-K chunks ──│        │          │
  │                    │                      │── build prompt    │         │          │
  │                    │                      │   (system + history + context + question)
  │                    │                      │── stream chat ───────────▶│          │
  │                    │                      │◀── token stream ──────────│          │
  │◀── SSE stream ─────│◀── tokens ──────────│                  │         │          │
  │   (token by token)  │                      │                  │         │          │
  │                    │                      │── save messages ──────────────────────▶│
  │◀── SSE [DONE] ─────│                     │                  │         │          │
```

### Analysis Flow

```text
User                  API              AnalysisEngine         Postgres  AzureOpenAI
  │                    │                      │                  │          │
  │── POST /analysis  ─▶│                     │                  │          │
  │   /run              │                     │                  │          │
  │  {company_ids,      │                     │                  │          │
  │   profile_id}       │                     │                  │          │
  │                    │── load financials ────────────────────────▶│       │
  │                    │── load criteria ──────────────────────────▶│       │
  │                    │── run engine ────────▶│                  │          │
  │                    │                      │── compute formulas│         │
  │                    │                      │   (per year, per criterion) │
  │                    │                      │── evaluate thresholds      │
  │                    │                      │── detect trends   │         │
  │                    │                      │── compute scores  │         │
  │                    │◀── AnalysisReport ───│                  │          │
  │                    │── generate summary ──────────────────────────────▶│
  │                    │◀── AI narrative ─────────────────────────────────│
  │                    │── save results ──────────────────────────▶│       │
  │◀── 200 OK ────────│   (full report)      │                  │          │
```

---

## Expression Parser Specification

```yaml
expression_parser:
  supported_operators: ["+", "-", "*", "/", "^", ">", ">=", "<", "<="]
  supported_functions:
    abs: {args: 1, description: "Absolute value"}
    min: {args: 2, description: "Minimum of two values"}
    max: {args: 2, description: "Maximum of two values"}
    avg: {args: "variadic", description: "Average of values"}

  field_reference_pattern: "(income_statement|balance_sheet|cash_flow)\\.[a-z_]+"
  prev_reference_pattern: "prev\\((.+?)(?:,\\s*(\\d+))?\\)"

  validation_rules:
    - All field references must correspond to known financial data fields
    - Division by zero must be handled (return null)
    - prev() lookback must not exceed available data
    - Parentheses must be balanced
    - Expression must return a numeric value

  error_messages:
    unknown_field: "Unknown financial field: '{field}'. Available fields: ..."
    division_by_zero: "Division by zero encountered for period {year}"
    unbalanced_parens: "Unbalanced parentheses in expression"
    syntax_error: "Syntax error at position {pos}: {detail}"
```

### Custom Formula Examples

```yaml
custom_formulas:
  - name: "Custom ROIC"
    expression: >
      income_statement.operating_income * (1 - 0.21) /
      (balance_sheet.total_assets - balance_sheet.total_current_liabilities
       - balance_sheet.cash_and_equivalents)

  - name: "Revenue CAGR 3Y"
    expression: >
      (income_statement.revenue / prev(income_statement.revenue, 3)) ^ (1/3) - 1

  - name: "Capex to Revenue"
    expression: >
      abs(cash_flow.capital_expenditure) / income_statement.revenue
```

---

## Frontend Specification

### Page Structure

```text
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (persistent)         │  MAIN CONTENT                   │
│  ┌─────────────────────────┐  │  ┌──────────────────────────┐   │
│  │ 🏠 Dashboard            │  │  │  PAGE CONTENT            │   │
│  │ 🏢 Companies            │  │  │  (varies by route)       │   │
│  │   ├── AAPL              │  │  │                          │   │
│  │   ├── MSFT              │  │  │                          │   │
│  │   ├── GOOGL             │  │  │                          │   │
│  │   └── + Add Company     │  │  │                          │   │
│  │ 📊 Analysis Profiles    │  │  │                          │   │
│  │ ⚙️ Settings             │  │  │                          │   │
│  └─────────────────────────┘  │  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Pages

```yaml
pages:
  /dashboard:
    description: Overview of all companies with quick stats
    components:
      - CompanyGrid (cards: ticker, name, doc count, readiness, last analysis score)
      - QuickActions (add company, run analysis)
      - RecentActivity (latest chats, uploads, analyses)

  /companies:
    description: Company list with search and filters
    components: [SearchBar, CompanyTable (sortable, filterable), AddCompanyModal]

  /companies/{id}:
    description: Company detail page with tabs
    tabs:
      overview: [CompanyHeader, FilingSummaryCard, FinancialSummaryCard, RecentChatSessions]
      documents: [DocumentTimeline, DocumentTable, UploadButton → UploadModal, FetchFromSECButton → FetchModal]
      financials: [PeriodSelector, FinancialDataTable, MetricCharts, ExportCSVButton]
      chat: [ChatSessionList (sidebar), ChatInterface, SourcesPanel (collapsible)]
      analysis: [ProfileSelector, RunAnalysisButton, ScoreCard, CriteriaTable, TrendCharts, AISummary, HistoricalResults]

  /analysis/profiles:
    description: Manage analysis profiles
    components: [ProfileList, ProfileEditor, CriteriaBuilder, FormulaSelector, ThresholdInput, WeightSlider]

  /analysis/compare:
    description: Multi-company comparison
    components: [CompanySelector (multi-select), ProfileSelector, ComparisonTable, RankingChart]

  /settings:
    description: System configuration
    components: [LLMSettings, EmbeddingSettings, IngestionSettings, APIKeyManagement]
```

### Chat Interface Specification

```yaml
chat_interface:
  layout:
    left_panel: (30% width, collapsible)
      - SessionList (grouped by date: today, this week, older)
      - NewChatButton
    main_panel: (70% width)
      - MessageList (scrollable, auto-scroll on new tokens)
        - UserMessage: right-aligned, blue bubble
        - AssistantMessage: left-aligned, white bubble, markdown rendered
        - SourcesAccordion: collapsible below assistant message
          - SourceChip: "📄 10-K FY2024 Item 1A (89%)" — clickable
          - SourceDetail: shows chunk text when expanded
      - InputArea (bottom, sticky)
        - TextArea (auto-resize, shift+enter for newlines, enter to send)
        - SendButton
        - RetrievalConfigToggle (expandable panel for top_k, filters)

  streaming_behavior:
    - Show typing indicator while waiting for first token
    - Render tokens as they arrive (append to message)
    - Parse markdown incrementally
    - Show sources after full response is received
    - Enable copy button on completed messages
    - Show token count on completed messages

  error_handling:
    - SSE connection drop: "Connection lost. Retry?" with button
    - LLM error: error message in red banner, preserve input
    - No sources found: info banner "No relevant filings found"
```

---

## Container Apps Configuration

```yaml
# Production resource allocations (dev overrides below)
api:
  image: ${ACR_LOGIN_SERVER}/investorinsights-api:${IMAGE_TAG}
  resources: {cpu: 1.0, memory: 2Gi}
  scale: {minReplicas: 1, maxReplicas: 5, http_concurrency: 50}
  ingress: {external: true, targetPort: 8000}
  probes:
    liveness: {path: /api/v1/health, periodSeconds: 30}
    readiness: {path: /api/v1/health, initialDelaySeconds: 10}

worker:
  image: ${ACR_LOGIN_SERVER}/investorinsights-api:${IMAGE_TAG}
  command: ["celery", "-A", "app.worker.celery_app", "worker",
            "--loglevel=info", "--concurrency=4",
            "--queues=ingestion,analysis,sec_fetch",
            "--max-tasks-per-child=50"]
  resources: {cpu: 2.0, memory: 4Gi}
  scale: {minReplicas: 1, maxReplicas: 5, redis_queue_length: 10}

frontend:
  image: ${ACR_LOGIN_SERVER}/investorinsights-frontend:${IMAGE_TAG}
  resources: {cpu: 0.5, memory: 1Gi}
  scale: {minReplicas: 1, maxReplicas: 3}
  ingress: {external: true, targetPort: 3000}

qdrant:
  image: qdrant/qdrant:v1.9.7
  resources: {cpu: 1.0, memory: 4Gi}
  scale: {minReplicas: 1, maxReplicas: 1}
  volumes: [{name: qdrant-data, storageType: AzureFile, mountPath: /qdrant/storage}]
  ingress: {external: false, targetPort: 6333}

# Development overrides (budget ≤ $50/month):
development_overrides:
  api:       {cpu: 0.25, memory: 0.5Gi, minReplicas: 0, maxReplicas: 1}
  worker:    {cpu: 0.5,  memory: 1Gi,   minReplicas: 0, maxReplicas: 2, concurrency: 2}
  frontend:  {cpu: 0.25, memory: 0.5Gi, minReplicas: 0, maxReplicas: 1}
  qdrant:    {cpu: 0.25, memory: 1Gi,   minReplicas: 0, maxReplicas: 1}
  redis:     {image: "redis:7-alpine", cpu: 0.25, memory: 0.5Gi, minReplicas: 0, maxReplicas: 1}
```

## Dockerfiles

### Backend

```dockerfile
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libmupdf-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN adduser --disabled-password --gecos "" appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Custom expression parser DSL | Users need flexible formula definitions beyond built-in list | Hard-coding all possible formulas insufficient for custom criteria |
| Celery + Redis (extra container) | Async ingestion requires robust task queue with retries/dead-letter | Simple background threads lack persistence, monitoring, retry logic |
| Qdrant (extra container) | Per-company collection isolation, filtered HNSW search at 500K+ vectors | pgvector lacks metadata-filtered search performance and collection isolation |

### Complexity Overview (informational)

| Area | Complexity | Notes |
|------|-----------|-------|
| Ingestion pipeline (parse/split/chunk/embed) | High | Multiple file formats, section regex, XBRL mapping, async orchestration |
| RAG chat agent | High | Retrieval tuning, prompt engineering, streaming SSE, conversation context |
| Financial analysis engine | Medium-High | Expression parser DSL, 25+ formulas, trend detection, scoring |
| Azure infrastructure (Bicep) | Medium | 12 modules, 2 environments, managed identity wiring |
| Frontend (Next.js) | Medium | Streaming chat UI, data tables, charts, 7+ pages |
| Company/document CRUD | Low | Standard REST with file upload |
| Auth (API key V1) | Low | Single key, constant-time comparison |
