# InvestorInsights — Developer Guide

> Comprehensive technical reference for developers working on the InvestorInsights platform.
> Last updated: 2026-03-14 · Version 1.0.0

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack](#2-technology-stack)
3. [Local Development Setup](#3-local-development-setup)
4. [Project Structure](#4-project-structure)
5. [Backend Deep Dive](#5-backend-deep-dive)
   - [Configuration](#51-configuration)
   - [Application Factory & Lifespan](#52-application-factory--lifespan)
   - [API Layer](#53-api-layer)
   - [Authentication & Middleware](#54-authentication--middleware)
   - [Dependency Injection](#55-dependency-injection)
   - [Database & ORM](#56-database--orm)
   - [Repository Pattern](#57-repository-pattern)
   - [Service Layer](#58-service-layer)
   - [Ingestion Pipeline](#59-ingestion-pipeline)
   - [XBRL Financial Extraction](#510-xbrl-financial-extraction)
   - [RAG Chat System](#511-rag-chat-system)
   - [Analysis Engine](#512-analysis-engine)
   - [Expression Parser](#513-expression-parser)
   - [Celery Workers](#514-celery-workers)
   - [External Clients & Circuit Breakers](#515-external-clients--circuit-breakers)
   - [Observability](#516-observability)
6. [Frontend Deep Dive](#6-frontend-deep-dive)
   - [App Router & Pages](#61-app-router--pages)
   - [Component Architecture](#62-component-architecture)
   - [API Client](#63-api-client)
   - [SSE Streaming](#64-sse-streaming)
   - [State Management](#65-state-management)
7. [Database Schema](#7-database-schema)
8. [API Reference](#8-api-reference)
9. [Testing](#9-testing)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [CI/CD Pipeline](#11-cicd-pipeline)
12. [Coding Standards](#12-coding-standards)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Architecture Overview

InvestorInsights is a full-stack AI-powered financial analysis platform for SEC filings. The system follows a layered architecture with clear separation of concerns:

```
┌──────────────────────────────────────────────────────────────┐
│                    Next.js Frontend (React 19)               │
│          Dashboard · Company Detail · Analysis · Chat        │
└─────────────────────────┬────────────────────────────────────┘
                          │  HTTP/REST + SSE
┌─────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend (Python)                   │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ API Layer│ │  Services  │ │  RAG Chat│ │Analysis Engine│  │
│  └────┬─────┘ └─────┬──────┘ └────┬─────┘ └──────┬───────┘  │
│       │             │             │               │          │
│  ┌────▼─────────────▼─────────────▼───────────────▼───────┐  │
│  │                   Repository Layer                     │  │
│  └────────────────────────┬───────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐  ┌────────▼───────┐  ┌────────▼───────┐
│  PostgreSQL  │  │     Qdrant     │  │      Redis     │
│  (10 tables) │  │ (vector store) │  │ (Celery broker)│
└──────────────┘  └────────────────┘  └───────┬────────┘
                                              │
                                     ┌────────▼────────┐
                                     │  Celery Workers  │
                                     │ ingestion │ XBRL │
                                     └─────────────────┘
        ┌─────────────────┐  ┌──────────────────┐
        │  Azure Blob     │  │   Azure OpenAI   │
        │  (file storage) │  │  (LLM/Embeddings)│
        └─────────────────┘  └──────────────────┘
```

### Data Flow Summary

1. **Company Registration** → User adds company by ticker → SEC EDGAR CIK auto-resolution
2. **Document Ingestion** → Upload PDF/HTML or auto-fetch from SEC EDGAR → Celery task → parse → clean → section split → chunk → embed → store in Qdrant + PostgreSQL
3. **Financial Extraction** → XBRL API → 42 tag mappings → normalised `statement_data` JSONB
4. **Chat (RAG)** → Query expansion → Qdrant vector search → context assembly → Azure OpenAI streaming → SSE to frontend
5. **Analysis** → Profile criteria → expression evaluation → OLS trend detection → binary scoring → A–F grading

---

## 2. Technology Stack

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | latest | Web framework, async-first |
| SQLAlchemy | 2.x (async) | ORM with `asyncpg` driver |
| Pydantic | 2.x | Validation, settings, schemas |
| Celery | 5.x | Background task processing |
| Redis | 7.x | Celery broker, rate-limit state |
| PostgreSQL | 16 | Primary database |
| Qdrant | 1.9+ | Vector similarity search |
| Azure OpenAI | GPT-4o / text-embedding-3-large | LLM and embeddings |
| structlog | latest | Structured JSON logging |
| tiktoken | latest | Token counting for chunking |
| PyMuPDF (fitz) | latest | PDF text extraction |
| httpx | latest | Async HTTP client (SEC EDGAR) |
| Alembic | latest | Database migrations |

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 16 (App Router) | React framework |
| React | 19 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | v4 | Utility-first styling |
| @tanstack/react-query | 5 | Server state + caching |
| recharts | 3 | Charts and visualisations |
| react-hook-form + zod | 7 / 4 | Form validation |
| react-markdown | 10 | Markdown rendering in chat |
| lucide-react | latest | Icon library |
| vitest | 4 | Unit testing |

### Infrastructure

| Technology | Purpose |
|-----------|---------|
| Azure Bicep | Infrastructure as Code (12 modules) |
| Docker | Multi-stage container builds |
| GitHub Actions | CI/CD pipeline |
| Azure Container Apps | Container hosting |
| Azure Key Vault | Secret management |
| Azure Blob Storage | File storage |
| Azure Database for PostgreSQL | Managed PostgreSQL |
| Azure Cache for Redis | Managed Redis |
| Azure Application Insights | Monitoring & APM |

---

## 3. Local Development Setup

### Prerequisites

- **Python 3.12+**
- **Node.js 20+** and **npm 10+**
- **Docker Desktop** (for PostgreSQL, Redis, Qdrant, Azurite)
- **Azure OpenAI** API key and endpoint (or OpenAI API key)

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd InvestorInsights

# 2. One-command setup (creates .env, venv, installs deps, starts Docker services, runs migrations)
make setup

# 3. Edit .env with your Azure OpenAI credentials
#    Required: API_KEY, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT
vim .env

# 4. Start infrastructure services (PostgreSQL, Redis, Qdrant, Azurite)
make up

# 5. Run database migrations
make migrate

# 6. Seed default analysis profile
make seed

# 7. Start the API server (with hot reload)
make dev
# → API available at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs

# 8. Start the frontend (in a separate terminal)
cd frontend && npm install && npm run dev
# → Frontend available at http://localhost:3000
```

### Docker Services (docker-compose.dev.yml)

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| PostgreSQL 16 | `investorinsights-postgres` | 5432 | Primary database |
| Redis 7 | `investorinsights-redis` | 6379 | Celery broker + rate limiting |
| Qdrant 1.9 | `investorinsights-qdrant` | 6333 (HTTP), 6334 (gRPC) | Vector store |
| Azurite | `investorinsights-azurite` | 10000 | Azure Blob Storage emulator |

### Running Celery Workers (optional, for background ingestion)

```bash
# Start worker listening on all queues
.venv/bin/celery -A app.worker.celery_app worker \
    --loglevel=info --concurrency=4 \
    --queues=ingestion,analysis,sec_fetch
```

### Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make setup` | First-time setup (venv, deps, Docker, migrations) |
| `make up` / `make down` | Start/stop Docker infrastructure |
| `make dev` | Start API server with hot reload |
| `make migrate` | Run Alembic migrations |
| `make migrate-new MESSAGE="..."` | Create new migration |
| `make seed` | Seed default analysis profile |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make test-e2e` | Run end-to-end tests |
| `make test-coverage` | Tests with coverage report (≥85% required) |
| `make lint` | Run Ruff + mypy |
| `make lint-fix` | Auto-fix lint issues |
| `make format` | Format code with Ruff |
| `make reset` | **Destructive** — wipe all data and rebuild |
| `make db-shell` | Open PostgreSQL interactive shell |
| `make flower` | Open Celery Flower monitoring UI |
| `make clean` | Remove caches and build artifacts |

---

## 4. Project Structure

```
InvestorInsights/
├── .env.example                # Environment variable template
├── .github/workflows/ci.yml   # CI/CD pipeline
├── Makefile                    # Development commands
├── pyproject.toml              # Python tooling config (Ruff, mypy, pytest)
├── docker-compose.dev.yml      # Local infrastructure services
│
├── backend/
│   ├── Dockerfile              # Multi-stage production image
│   ├── alembic.ini             # Alembic configuration
│   ├── requirements.txt        # Production Python dependencies
│   ├── requirements-dev.txt    # Development dependencies (pytest, etc.)
│   │
│   ├── alembic/
│   │   └── versions/           # Database migrations
│   │       ├── 001_initial_schema.py
│   │       └── 002_add_hot_path_indexes.py
│   │
│   ├── app/
│   │   ├── main.py             # FastAPI app factory + ASGI entry point
│   │   ├── config.py           # Pydantic BaseSettings (all env vars)
│   │   ├── dependencies.py     # FastAPI DI providers
│   │   │
│   │   ├── api/                # Route handlers (controllers)
│   │   │   ├── router.py       # Top-level router with auth dependency
│   │   │   ├── companies.py    # CRUD endpoints
│   │   │   ├── documents.py    # Upload, fetch-SEC, retry
│   │   │   ├── financials.py   # Financial data + CSV export
│   │   │   ├── chat.py         # SSE streaming chat
│   │   │   ├── analysis.py     # Profiles, run, compare, results
│   │   │   ├── health.py       # Health check (no auth)
│   │   │   ├── tasks.py        # Celery task status polling
│   │   │   ├── pagination.py   # Pagination query parameters
│   │   │   └── middleware/
│   │   │       ├── auth.py         # X-API-Key validation (HMAC)
│   │   │       ├── rate_limiter.py # Redis-backed sliding window
│   │   │       ├── request_id.py   # X-Request-ID injection
│   │   │       └── error_handler.py# Global exception → JSON mapping
│   │   │
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── base.py         # Declarative base + UUID/Timestamp mixins
│   │   │   ├── company.py      # companies table
│   │   │   ├── document.py     # documents table (with DocStatus enum)
│   │   │   ├── section.py      # document_sections table
│   │   │   ├── chunk.py        # document_chunks table
│   │   │   ├── financial.py    # financial_statements table
│   │   │   ├── session.py      # chat_sessions table
│   │   │   ├── message.py      # chat_messages table
│   │   │   ├── profile.py      # analysis_profiles table
│   │   │   ├── criterion.py    # analysis_criteria table
│   │   │   └── result.py       # analysis_results table
│   │   │
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── company.py      # CompanyCreate, CompanyRead, etc.
│   │   │   ├── document.py     # DocumentUpload, FetchSECRequest, etc.
│   │   │   ├── financial.py    # FinancialPeriod, FinancialsResponse
│   │   │   ├── chat.py         # ChatRequest, SSE event schemas
│   │   │   ├── analysis.py     # ProfileCreate, AnalysisRunRequest, etc.
│   │   │   └── common.py       # HealthResponse, pagination schemas
│   │   │
│   │   ├── db/
│   │   │   ├── session.py      # Engine init, async session factory
│   │   │   └── repositories/   # Data access layer
│   │   │       ├── company_repo.py
│   │   │       ├── document_repo.py
│   │   │       ├── financial_repo.py
│   │   │       ├── chat_repo.py
│   │   │       ├── profile_repo.py
│   │   │       └── result_repo.py
│   │   │
│   │   ├── services/           # Business logic layer
│   │   │   ├── company_service.py
│   │   │   ├── document_service.py
│   │   │   ├── financial_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── analysis_service.py
│   │   │   └── retrieval_service.py
│   │   │
│   │   ├── clients/            # External service clients
│   │   │   ├── circuit_breaker.py  # Circuit breaker state machine
│   │   │   ├── openai_client.py    # Azure OpenAI / OpenAI wrapper
│   │   │   ├── qdrant_client.py    # Vector store operations
│   │   │   ├── redis_client.py     # Redis + rate-limit helpers
│   │   │   ├── sec_client.py       # SEC EDGAR API client
│   │   │   └── storage_client.py   # Azure Blob / Azurite wrapper
│   │   │
│   │   ├── ingestion/          # Document processing pipeline
│   │   │   ├── pipeline.py     # Orchestrator (7-stage pipeline)
│   │   │   ├── chunker.py      # Token-aware recursive text splitter
│   │   │   ├── embedder.py     # Batch embedding generation
│   │   │   ├── section_splitter.py # Filing section detection
│   │   │   └── parsers/
│   │   │       ├── pdf_parser.py   # PyMuPDF-based extraction
│   │   │       ├── html_parser.py  # BeautifulSoup extraction
│   │   │       └── text_cleaner.py # Whitespace/encoding normalisation
│   │   │
│   │   ├── analysis/           # Financial analysis engine
│   │   │   ├── engine.py       # Pipeline orchestrator
│   │   │   ├── expression_parser.py # Recursive-descent formula parser
│   │   │   ├── formulas.py     # 28 built-in financial formulas
│   │   │   ├── scorer.py       # Binary scoring + grading
│   │   │   └── trend.py        # OLS trend detection
│   │   │
│   │   ├── rag/                # RAG chat system
│   │   │   ├── chat_agent.py   # Agent orchestrator (retrieve → prompt → stream)
│   │   │   └── prompt_builder.py # System prompt + context assembly
│   │   │
│   │   ├── xbrl/               # XBRL data extraction
│   │   │   ├── tag_registry.py # 42 XBRL→internal field mappings
│   │   │   ├── mapper.py       # SEC XBRL API data normalisation
│   │   │   └── period_selector.py # Fiscal period resolution
│   │   │
│   │   ├── worker/             # Celery task definitions
│   │   │   ├── celery_app.py   # Celery configuration
│   │   │   ├── callbacks.py    # Task lifecycle callbacks
│   │   │   └── tasks/
│   │   │       ├── ingestion_tasks.py
│   │   │       ├── analysis_tasks.py
│   │   │       └── sec_fetch_tasks.py
│   │   │
│   │   ├── observability/
│   │   │   └── logging.py      # structlog setup + sensitive data redaction
│   │   │
│   │   └── scripts/
│   │       └── seed_defaults.py # Seeds the default analysis profile
│   │
│   └── tests/
│       ├── conftest.py         # Shared fixtures
│       ├── factories.py        # Test data factories
│       ├── unit/               # 393 unit tests (no external deps)
│       ├── integration/        # 142 integration tests (Docker services)
│       └── e2e/                # 28 end-to-end tests (full stack)
│
├── frontend/
│   ├── Dockerfile              # Multi-stage Next.js production image
│   ├── next.config.ts          # Next.js configuration
│   ├── vitest.config.ts        # Vitest test configuration
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   │   ├── page.tsx        # Redirects to /dashboard
│   │   │   ├── layout.tsx      # Root layout (sidebar + providers)
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── companies/
│   │   │   │   ├── page.tsx         # Company list
│   │   │   │   └── [id]/page.tsx    # Company detail (5 tabs)
│   │   │   ├── analysis/
│   │   │   │   ├── profiles/page.tsx # Analysis profile management
│   │   │   │   └── compare/page.tsx  # Multi-company comparison
│   │   │   └── settings/page.tsx     # Application settings
│   │   │
│   │   ├── components/
│   │   │   ├── layout/         # Sidebar, PageHeader
│   │   │   ├── company/        # OverviewTab
│   │   │   ├── documents/      # DocumentsTab
│   │   │   ├── financials/     # FinancialsTab
│   │   │   ├── chat/           # ChatTab (SSE streaming)
│   │   │   ├── analysis/       # AnalysisTab
│   │   │   └── ui/             # Reusable UI primitives
│   │   │
│   │   ├── lib/
│   │   │   ├── api-client.ts   # Typed REST client
│   │   │   ├── sse-client.ts   # SSE streaming client
│   │   │   ├── format.ts       # Number/date formatting
│   │   │   └── utils.ts        # cn() utility for class merging
│   │   │
│   │   └── providers/
│   │       └── query-provider.tsx # React Query provider
│   │
│   └── tests/                  # 117 frontend tests (vitest)
│
├── infra/
│   ├── main.bicep              # Root Bicep deployment template
│   ├── modules/                # 12 Bicep modules
│   ├── parameters/             # dev.bicepparam, prod.bicepparam
│   └── scripts/                # deploy.sh, destroy.sh, seed-keyvault.sh
│
├── scripts/                    # setup.sh, seed.sh, reset.sh
├── specs/                      # Design specifications and reference docs
└── docs/                       # Operational documentation
```

---

## 5. Backend Deep Dive

### 5.1 Configuration

All configuration is managed through Pydantic `BaseSettings` in `backend/app/config.py`. Every setting maps 1:1 to an environment variable.

**Key design decisions:**
- `.env` file is loaded automatically in development
- In production, values come from Azure Key Vault → Container App environment
- Computed URLs (`database_url`, `qdrant_url`, `celery_broker_url`) are auto-built from component parts via `model_validator(mode="after")`
- LLM provider config is validated at startup (e.g., Azure OpenAI requires both `api_key` and `endpoint`)
- SEC EDGAR `user_agent` format is validated (must contain email)

```python
# Access settings anywhere via:
from app.config import get_settings
settings = get_settings()  # Cached singleton (lru_cache)
```

**Environment groupings:**

| Group | Example Variables | Notes |
|-------|------------------|-------|
| Application | `APP_ENV`, `LOG_LEVEL`, `API_KEY` | `API_KEY` is the auth token |
| Database | `DB_HOST`, `DB_PORT`, `DB_POOL_SIZE` | Pool sizing is per-worker |
| Qdrant | `QDRANT_HOST`, `QDRANT_API_KEY` | Optional API key |
| Azure Blob | `AZURE_STORAGE_CONNECTION_STRING` | Azurite in dev |
| Redis | `REDIS_URL`, `REDIS_SSL` | SSL on in production |
| Celery | `CELERY_BROKER_URL`, `WORKER_CONCURRENCY` | Auto-computed from Redis URL |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | Requires both for `azure_openai` provider |
| LLM | `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | Model-agnostic settings |
| RAG | `RAG_TOP_K`, `RAG_SCORE_THRESHOLD` | Retrieval tuning |
| Ingestion | `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_UPLOAD_SIZE_MB` | Chunking parameters |
| SEC EDGAR | `SEC_EDGAR_USER_AGENT` | Must include email per SEC policy |
| Rate Limits | `API_RATE_LIMIT_CRUD`, `API_RATE_LIMIT_CHAT` | Per-IP sliding window |

### 5.2 Application Factory & Lifespan

The FastAPI app is created by `create_app()` in `backend/app/main.py`:

```python
app = create_app()  # Module-level instance used by uvicorn: app.main:app
```

**Lifespan events:**
- **Startup:** Setup structured logging → initialise SQLAlchemy engine → record startup time
- **Shutdown:** Dispose the async engine (close all DB connections)

**Middleware stack** (registered in reverse order — outermost first):
1. `RequestIDMiddleware` — Injects `X-Request-ID` header on every response
2. `RateLimitMiddleware` — Redis-backed per-IP sliding window
3. `CORSMiddleware` — Permissive in dev, restrictive in production

**CORS:** In production, only `https://investorinsights.azurecontainerapps.io` is allowed. In development, `localhost:3000` and `localhost:8000` are permitted.

**OpenAPI docs** (`/docs`, `/redoc`) are disabled in production.

### 5.3 API Layer

All API endpoints live under `backend/app/api/`. The top-level router (`router.py`) mounts all sub-routers under `/api/v1` with the `require_api_key` dependency.

**Endpoint summary:**

| Module | Prefix | Endpoints |
|--------|--------|-----------|
| `companies.py` | `/api/v1/companies` | POST (create), GET (list), GET/:id (detail), PUT/:id (update), DELETE/:id |
| `documents.py` | `/api/v1/companies/{id}/documents` | POST (upload), GET (list), GET/:doc_id (detail), POST/:doc_id/retry, DELETE/:doc_id, POST/fetch-sec |
| `financials.py` | `/api/v1/companies/{id}/financials` | GET (list periods), GET/export (CSV) |
| `chat.py` | `/api/v1/companies/{id}/chat` | POST (SSE stream), GET/sessions (list), GET/sessions/:sid (detail), DELETE/sessions/:sid |
| `analysis.py` | `/api/v1/analysis` | Profiles CRUD, POST/run, POST/compare, GET/results, GET/results/:id, GET/results/:id/export, GET/formulas |
| `health.py` | `/api/v1/health` | GET (no auth, probes all dependencies) |
| `tasks.py` | `/api/v1/tasks` | GET/:task_id (Celery task status) |

### 5.4 Authentication & Middleware

**Authentication:** Static API key via `X-API-Key` header.
- Validated with `hmac.compare_digest()` for constant-time comparison (prevents timing attacks)
- Key is loaded from `Settings.api_key` (sourced from `API_KEY` env var / Key Vault)
- The `/api/v1/health` endpoint opts out of auth

**Rate Limiting** (`rate_limiter.py`):
- Redis-backed sliding window, per client IP
- Two tiers: CRUD (100/min default) and Chat (20/min default)
- Chat endpoints identified by `/chat` in the URL path
- **Fails open** — if Redis is unavailable, requests are allowed
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 429 responses include `Retry-After` header

**Request ID** (`request_id.py`):
- Generates a UUID for every request
- Injected as `X-Request-ID` response header
- Available in structlog context for log correlation

**Error Handler** (`error_handler.py`):
- Maps exceptions to consistent JSON error responses
- Custom exception classes: `NotFoundError`, `ValidationError`, `ConflictError`
- Catches unhandled exceptions and returns 500 with request ID

### 5.5 Dependency Injection

FastAPI's DI system is configured in `backend/app/dependencies.py`:

| Dependency | Type | Scope | Description |
|-----------|------|-------|-------------|
| `DbSessionDep` | `AsyncSession` | Per-request | Auto-committed, auto-closed |
| `SettingsDep` | `Settings` | Singleton | Cached via `lru_cache` |
| `StorageDep` | `StorageClient` | Singleton | Azure Blob / Azurite client |

Route handlers use `Annotated` type aliases for clean signatures:

```python
async def create_company(
    payload: CompanyCreate,
    session: DbSessionDep,  # ← Annotated[AsyncSession, Depends(get_db)]
) -> CompanyRead:
```

### 5.6 Database & ORM

**Engine initialisation** (`db/session.py`):
- `init_engine(settings)` creates the async SQLAlchemy engine with connection pooling
- Pool configuration: `pool_size` and `max_overflow` per worker (total = workers × (size + overflow))
- `get_async_session()` is an async generator yielding scoped sessions

**ORM base** (`models/base.py`):
- `Base` — SQLAlchemy `DeclarativeBase` with PostgreSQL naming conventions
- `UUIDMixin` — UUID primary key with `gen_random_uuid()` server default
- `TimestampMixin` — `created_at` and `updated_at` with server-side timestamps

**10 ORM models:**

| Model | Table | Key Columns |
|-------|-------|-------------|
| `Company` | `companies` | ticker (unique), name, cik, sector, industry, metadata JSONB |
| `Document` | `documents` | company_id FK, doc_type enum, fiscal_year, status enum, storage_key |
| `DocumentSection` | `document_sections` | document_id FK, section_key, title, content |
| `DocumentChunk` | `document_chunks` | document_id FK, company_id FK, section_key, content, token_count |
| `FinancialStatement` | `financial_statements` | company_id FK, fiscal_year, statement_data JSONB, source |
| `ChatSession` | `chat_sessions` | company_id FK, title, message_count |
| `ChatMessage` | `chat_messages` | session_id FK, role enum, content, sources JSONB |
| `AnalysisProfile` | `analysis_profiles` | name, description, is_default, version |
| `AnalysisCriterion` | `analysis_criteria` | profile_id FK, name, formula, comparison, threshold, weight |
| `AnalysisResult` | `analysis_results` | company_id FK, profile_id FK, score, grade, criteria_results JSONB |

**Migrations:** Alembic with two migration files:
- `001_initial_schema.py` — All 10 tables
- `002_add_hot_path_indexes.py` — 23 performance indexes

### 5.7 Repository Pattern

Each entity has a repository class in `backend/app/db/repositories/`. Repositories encapsulate all SQL queries and return ORM model instances.

```python
class CompanyRepository:
    def __init__(self, session: AsyncSession): ...
    async def create(self, data: dict) -> Company: ...
    async def get_by_id(self, id: UUID) -> Company | None: ...
    async def get_by_ticker(self, ticker: str) -> Company | None: ...
    async def list(self, *, search, sector, sort_by, limit, offset) -> tuple[list[Company], int]: ...
    async def update(self, company: Company, data: dict) -> Company: ...
    async def delete(self, company: Company) -> None: ...
```

Repositories are instantiated inside service classes, never called directly from route handlers.

### 5.8 Service Layer

Business logic lives in `backend/app/services/`. Services coordinate repositories, external clients, and domain logic.

| Service | Key Responsibilities |
|---------|---------------------|
| `CompanyService` | CRUD + SEC EDGAR CIK auto-resolution + bulk summary stats |
| `DocumentService` | Upload to blob storage + status transitions + Celery task dispatch |
| `FinancialService` | XBRL extraction orchestration + financial data queries |
| `ChatService` | Session management + message persistence + history retrieval |
| `AnalysisService` | Profile management + analysis execution + result storage + comparison |
| `RetrievalService` | Query expansion + Qdrant vector search + deduplication |

### 5.9 Ingestion Pipeline

The ingestion pipeline (`ingestion/pipeline.py`) processes documents through 7 stages:

```
Download from Blob → Validate (magic bytes) → Parse (PDF/HTML) → Clean text
    → Split into sections → Chunk (token-aware) → Embed + upsert to Qdrant
```

**Chunking strategy** (`chunker.py`):
- Target: 768 tokens per chunk, 128 token overlap
- Recursive splitting: paragraphs → sentences → words
- Token counting via tiktoken (`cl100k_base` encoding)
- Each chunk retains section metadata for citation

**Section splitting** (`section_splitter.py`):
- Detects SEC filing sections (Item 1, Item 1A, Item 7, etc.)
- Different patterns for 10-K, 10-Q, 8-K filing types

**Document status machine:**
```
UPLOADED → PARSING → CHUNKING → EMBEDDING → READY
                                            ↓ (on failure)
                                          FAILED
```

### 5.10 XBRL Financial Extraction

The XBRL subsystem (`xbrl/`) extracts structured financial data from SEC EDGAR's XBRL API:

1. **Tag Registry** (`tag_registry.py`) — 42 internal field names mapped to prioritised XBRL tag lists across income statement, balance sheet, and cash flow
2. **Mapper** (`mapper.py`) — Fetches companyfacts JSON from SEC, applies tag mappings, normalises into `statement_data` JSONB structure
3. **Period Selector** (`period_selector.py`) — Resolves annual vs quarterly periods from XBRL date ranges

**Data structure stored in `financial_statements.statement_data`:**
```json
{
  "income_statement": { "revenue": 394328000000, "net_income": 96995000000, ... },
  "balance_sheet": { "total_assets": 352583000000, "total_equity": 62146000000, ... },
  "cash_flow": { "operating_cash_flow": 110543000000, ... }
}
```

### 5.11 RAG Chat System

The RAG system (`rag/`) implements retrieval-augmented generation with streaming:

**CompanyChatAgent** (`chat_agent.py`) orchestrates:
1. **Out-of-scope detection** — Regex patterns reject investment advice, stock predictions, off-topic queries
2. **Retrieval** — `RetrievalService` performs query expansion + Qdrant similarity search
3. **Context assembly** — Retrieved chunks are formatted with metadata headers
4. **Prompt building** — System prompt + context + conversation history + user question
5. **LLM streaming** — Azure OpenAI chat completion stream
6. **Citation extraction** — Regex parses `[Source: ...]` patterns from generated text

**Event types yielded during streaming:**
- `SourcesEvent` — Retrieved chunks (sent before LLM tokens)
- `TokenEvent` — Individual tokens from the LLM
- `DoneEvent` — Final message with metadata (token count, citations, model)

**SSE wire format** (sent to frontend):
```
event: session
data: {"session_id": "...", "title": "..."}

event: sources
data: {"sources": [...]}

event: token
data: {"token": "The company's revenue..."}

event: done
data: {"message_id": "...", "token_count": 234}
```

**Query expansion** (`retrieval_service.py`):
- LLM generates 2–3 alternative search queries
- All queries are embedded and searched in parallel
- Results are deduplicated by chunk ID and re-ranked by score
- Graceful degradation: if expansion fails, original query is used alone

### 5.12 Analysis Engine

The analysis engine (`analysis/`) evaluates companies against configurable criteria profiles:

**Pipeline** (`engine.py`):
1. Load financial data by year from `statement_data` JSONB
2. For each criterion: resolve formula → compute across years → detect trend → evaluate threshold → score
3. Aggregate: sum weighted scores → compute percentage → assign grade

**Scoring** (`scorer.py`):
- Binary pass/fail per criterion × weight
- No-data criteria excluded from max possible score
- Grade thresholds: **A** ≥90%, **B** ≥75%, **C** ≥60%, **D** ≥40%, **F** <40%

**Trend detection** (`trend.py`):
- OLS linear regression on yearly values
- Minimum 3 data points required
- Normalised slope = slope / |mean|
- Classification: >+3% → "improving", <−3% → "declining", else → "stable"

**28 built-in formulas** (`formulas.py`) across 7 categories:
- Profitability: gross_margin, operating_margin, net_margin, ROE, ROA, ROIC
- Growth: revenue_growth, earnings_growth, operating_income_growth, free_cash_flow_growth
- Liquidity: current_ratio, quick_ratio, cash_ratio
- Solvency: debt_to_equity, debt_to_assets, interest_coverage
- Efficiency: asset_turnover, inventory_turnover, receivables_turnover, payables_turnover
- Cash Flow Quality: operating_cash_flow_ratio, free_cash_flow_margin, capex_to_revenue, cash_conversion
- Dividend: dividend_payout_ratio, dividend_yield, earnings_retention

### 5.13 Expression Parser

The expression parser (`expression_parser.py`) is a recursive-descent parser supporting custom formulas:

**Supported syntax:**
- Field references: `income_statement.revenue`
- Arithmetic: `+ - * / ^`
- Parentheses: `(expr)`
- Functions: `abs(x)`, `min(a, b)`, `max(a, b)`, `avg(a, b, ...)`
- Previous period: `prev(field)`, `prev(field, lookback)`
- Numeric literals and unary minus

**Grammar (EBNF):**
```
expr       → term (( '+' | '-' ) term)*
term       → power (( '*' | '/' ) power)*
power      → unary ( '^' power )?
unary      → '-' unary | call
call       → IDENT '(' args ')' | atom
args       → expr ( ',' expr )*
atom       → NUMBER | field_ref | '(' expr ')'
field_ref  → IDENT '.' IDENT
```

**Pipeline:** Lexer → Parser (AST) → Evaluator with `FormulaContext` that resolves field references from year-indexed financial data.

### 5.14 Celery Workers

Three task queues with dedicated routing:

| Queue | Tasks | Description |
|-------|-------|-------------|
| `ingestion` | `ingest_document`, `reprocess_document` | Document parsing, chunking, embedding |
| `analysis` | `run_analysis_task` | Background analysis execution |
| `sec_fetch` | `fetch_sec_filings` | SEC EDGAR auto-fetch + ingestion |

**Configuration highlights:**
- `task_acks_late = True` — Tasks acknowledged only after completion (at-least-once delivery)
- `worker_prefetch_multiplier = 1` — One task at a time per worker process
- `worker_max_tasks_per_child = 50` — Workers recycled to prevent memory leaks
- JSON serialisation only (no pickle)
- Result TTL: 1 hour

**XBRL integration:** After document ingestion, the `ingest_document` task attempts best-effort XBRL financial extraction. Failures are logged but never block the text ingestion pipeline.

### 5.15 External Clients & Circuit Breakers

All external services are accessed through client wrappers in `backend/app/clients/`:

| Client | Service | Circuit Breaker Config |
|--------|---------|----------------------|
| `OpenAIClient` | Azure OpenAI / OpenAI | 5 failures → 60s recovery |
| `VectorStoreClient` | Qdrant | 3 failures → 30s recovery |
| `SECClient` | SEC EDGAR | 10 failures → 300s recovery |
| `StorageClient` | Azure Blob / Azurite | None (critical path) |
| `RedisClient` | Redis | None (fails open) |

**Circuit breaker states:** Closed → Open → Half-Open

When a circuit opens:
- `CircuitOpenError` is raised with `retry_after` seconds
- Callers handle gracefully (e.g., chat unavailable, CRUD still works)
- After recovery timeout, one probe request is allowed (half-open)
- Success closes the circuit; failure re-opens it

**Resilience guarantees:**
- Azure OpenAI down → CRUD + analysis still function (NFR-401)
- Qdrant down → CRUD + financial analysis still function (NFR-402)
- Redis down → Rate limiting disabled (fails open), Celery tasks queue locally

### 5.16 Observability

**Structured logging** (`observability/logging.py`):
- Uses `structlog` with JSON output in production, pretty console in development
- Automatic fields: timestamp, level, service name, logger name
- Request-scoped context: `request_id`, `company_id`, `document_id`
- **Sensitive data redaction** — API keys, passwords, connection strings, and other secrets are automatically redacted from all log output

**Health check** (`api/health.py`):
- Probes all 5 dependencies in parallel (PostgreSQL, Qdrant, Blob, Redis, LLM)
- Returns per-component status and latency
- Overall: `healthy` (all pass), `degraded` (partial failure, DB up), `unhealthy` (DB down)

**Azure Application Insights** integration via OpenTelemetry (configured in production).

---

## 6. Frontend Deep Dive

### 6.1 App Router & Pages

The frontend uses Next.js 16 App Router with client-side rendering (`"use client"` directives):

| Route | Page | Description |
|-------|------|-------------|
| `/` | `page.tsx` | Redirects to `/dashboard` |
| `/dashboard` | `dashboard/page.tsx` | Portfolio overview, summary cards, company grid |
| `/companies` | `companies/page.tsx` | Company list with search, filter, sort, add dialog |
| `/companies/[id]` | `companies/[id]/page.tsx` | Company detail with 5 tabs |
| `/analysis/profiles` | `analysis/profiles/page.tsx` | Analysis profile management |
| `/analysis/compare` | `analysis/compare/page.tsx` | Multi-company comparison table |
| `/settings` | `settings/page.tsx` | Health check, system info |

### 6.2 Component Architecture

**Layout:**
- `Sidebar` — Collapsible navigation (mobile hamburger + desktop fixed sidebar)
- `PageHeader` — Consistent title + description + action buttons

**Company detail tabs** (`/companies/[id]`):

| Tab | Component | Features |
|-----|-----------|----------|
| Overview | `OverviewTab` | Company metadata, document summary, financial summary |
| Documents | `DocumentsTab` | Document list, SEC auto-fetch button, upload, retry, delete |
| Financials | `FinancialsTab` | Financial data table, CSV export |
| Chat | `ChatTab` | Streaming AI chat, session list, source citations, markdown rendering |
| Analysis | `AnalysisTab` | Run analysis, view results, grade badges, criteria detail |

**UI primitives** (`components/ui/`):
- `Button`, `Card`, `Badge`, `Input`, `Spinner`, `ErrorBanner`, `EmptyState`
- All styled with Tailwind CSS utility classes

### 6.3 API Client

`frontend/src/lib/api-client.ts` provides a fully typed REST client:

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Every request includes X-API-Key header
async function request<T>(path: string, options?: RequestInit): Promise<T>

// Namespaced API functions:
companiesApi.list({ search, sector, sort_by, limit, offset })
companiesApi.get(id)
companiesApi.create(data)
documentsApi.list(companyId, params)
documentsApi.fetchSec(companyId, data)
chatApi.listSessions(companyId)
chatApi.getSession(companyId, sessionId)
analysisApi.listProfiles()
analysisApi.runAnalysis({ company_ids, profile_id })
analysisApi.compare({ company_ids, profile_id })
financialsApi.get(companyId)
healthApi.check()
```

### 6.4 SSE Streaming

The SSE client (`frontend/src/lib/sse-client.ts`) handles streaming chat responses:

```typescript
const controller = streamChat(companyId, { message, session_id }, {
  onSession: (data) => { /* new/existing session */ },
  onSources: (data) => { /* retrieved context chunks */ },
  onToken: (data) => { /* append token to message */ },
  onDone: (data) => { /* completion with metadata */ },
  onError: (data) => { /* error handling */ },
});

// Cancel the stream:
controller.abort();
```

Uses native `fetch()` with `ReadableStream` for broad browser compatibility.

### 6.5 State Management

- **Server state:** `@tanstack/react-query` with `queryKey` arrays for automatic cache invalidation
- **Form state:** `react-hook-form` + `zod` validators
- **Local state:** React `useState` for UI concerns (active tab, dialogs, etc.)
- **No global state store** — data flows top-down from React Query caches

---

## 7. Database Schema

### Entity-Relationship Overview

```
companies ──1:N──→ documents ──1:N──→ document_sections
    │                    └──1:N──→ document_chunks
    │
    ├──1:N──→ financial_statements
    ├──1:N──→ chat_sessions ──1:N──→ chat_messages
    └──1:N──→ analysis_results

analysis_profiles ──1:N──→ analysis_criteria
                   └──1:N──→ analysis_results
```

### Key Indexes (23 total, from migration 002)

- `companies.ticker` — Unique
- `companies.cik` — For SEC lookups
- `documents(company_id, doc_type, fiscal_year)` — Composite for filtering
- `documents(status)` — For queue processing
- `document_chunks(company_id)` — For RAG retrieval metadata
- `financial_statements(company_id, fiscal_year)` — For analysis data loading
- `chat_sessions(company_id, updated_at DESC)` — For session listing
- `analysis_results(company_id, created_at DESC)` — For result history

---

## 8. API Reference

### Authentication

All endpoints (except `/api/v1/health`) require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/companies
```

### Pagination

List endpoints accept standard pagination parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | 20 | Items per page (1–100) |
| `offset` | 0 | Skip count |
| `sort_by` | varies | Sort field name |
| `sort_order` | `desc` | `asc` or `desc` |

Response format:
```json
{
  "items": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### Error Format

All errors follow a consistent structure:

```json
{
  "status": 404,
  "error": "not_found",
  "message": "Company not found",
  "details": [],
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Key Endpoints Quick Reference

```
POST   /api/v1/companies                              Create company
GET    /api/v1/companies                              List companies
GET    /api/v1/companies/{id}                          Company detail
PUT    /api/v1/companies/{id}                          Update company
DELETE /api/v1/companies/{id}?confirm=true             Delete company

POST   /api/v1/companies/{id}/documents               Upload document
POST   /api/v1/companies/{id}/documents/fetch-sec      Auto-fetch from SEC
GET    /api/v1/companies/{id}/documents               List documents
POST   /api/v1/companies/{id}/documents/{doc}/retry    Retry failed ingestion

GET    /api/v1/companies/{id}/financials               List financial periods
GET    /api/v1/companies/{id}/financials/export        CSV export

POST   /api/v1/companies/{id}/chat                     Chat (SSE stream)
GET    /api/v1/companies/{id}/chat/sessions            List chat sessions
GET    /api/v1/companies/{id}/chat/sessions/{sid}      Session detail

POST   /api/v1/analysis/run                            Run analysis
POST   /api/v1/analysis/compare                        Compare companies
GET    /api/v1/analysis/profiles                       List profiles
POST   /api/v1/analysis/profiles                       Create profile
GET    /api/v1/analysis/results                        List results
GET    /api/v1/analysis/formulas                       List built-in formulas

GET    /api/v1/health                                  Health check (no auth)
GET    /api/v1/tasks/{task_id}                         Celery task status
```

---

## 9. Testing

### Test Structure

```
backend/tests/
├── conftest.py           # Shared fixtures (anyio backend)
├── factories.py          # Test data factories
├── unit/                 # 393 tests — fast, no external deps
│   ├── test_analysis.py
│   ├── test_chunker.py
│   ├── test_config.py
│   ├── test_expression_parser.py
│   ├── test_formulas.py
│   ├── test_health.py
│   ├── test_pipeline.py
│   ├── test_prompt_builder.py
│   ├── test_scorer.py
│   ├── test_section_splitter.py
│   ├── test_trend.py
│   ├── test_xbrl_mapper.py
│   ├── test_xbrl_no_data.py
│   └── ...
├── integration/          # 142 tests — require Docker services
│   ├── test_company_api.py
│   ├── test_document_api.py
│   ├── test_chat_api.py
│   ├── test_analysis_api.py
│   ├── test_rate_limiting.py
│   └── ...
└── e2e/                  # 28 tests — full stack workflows
    └── test_e2e_journeys.py

frontend/tests/
├── setup.ts              # Test setup
├── components/           # Component tests
└── lib/                  # Library utility tests
```

### Running Tests

```bash
# All tests
make test

# By category
make test-unit
make test-integration
make test-e2e

# With coverage (85% minimum enforced)
make test-coverage

# Frontend tests
cd frontend && npm test
cd frontend && npm run test:coverage
```

### Test Configuration

**pytest** (configured in `pyproject.toml`):
- `asyncio_mode = "auto"` — Async tests run automatically
- `timeout = 30` — 30-second default timeout per test
- Markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`

**Coverage:**
- Source: `backend/app/`
- Excludes: `worker/`, `tests/`, `alembic/`
- Minimum: 85%
- `if TYPE_CHECKING:` blocks excluded

### Writing Tests

**Unit tests** should mock all external dependencies:
```python
@pytest.mark.unit
async def test_run_analysis_empty_data():
    result = run_analysis(criteria=[], data_by_year={})
    assert result.grade == "F"
    assert result.criteria_count == 0
```

**Integration tests** use Docker services and a real database:
```python
@pytest.mark.integration
async def test_create_company_api(client: TestClient):
    response = client.post("/api/v1/companies", json={"ticker": "AAPL"})
    assert response.status_code == 201
```

---

## 10. Infrastructure & Deployment

### Azure Resources (Bicep)

12 Bicep modules in `infra/modules/`:

| Module | Azure Resource | Purpose |
|--------|---------------|---------|
| `resource-group.bicep` | Resource Group | Logical container |
| `networking.bicep` | VNet + Subnets | Network isolation |
| `postgresql.bicep` | Azure Database for PostgreSQL Flexible Server | Primary database |
| `redis.bicep` | Azure Cache for Redis | Celery broker + rate limiting |
| `storage.bicep` | Storage Account + Blob containers | File storage |
| `container-registry.bicep` | Azure Container Registry | Docker image registry |
| `container-apps.bicep` | Container Apps Environment + 4 apps | API, Worker, Frontend, Qdrant |
| `openai.bicep` | Azure OpenAI | GPT-4o + text-embedding-3-large |
| `key-vault.bicep` | Azure Key Vault | Secret management |
| `app-insights.bicep` | Application Insights | APM + monitoring |
| `log-analytics.bicep` | Log Analytics Workspace | Centralised logging |
| `alerts.bicep` | Alert Rules | Budget + health alerts |

### Environment Tiers

| Parameter | Dev | Production |
|-----------|-----|------------|
| PostgreSQL SKU | Burstable B2s | GP_Gen5_2 |
| Redis SKU | Basic C0 | Standard C1 |
| API Workers | 1 | 4 |
| LLM Model | gpt-4o-mini | gpt-4o |
| Budget | ≤$50/month | — |

### Docker Images

**Backend** (`backend/Dockerfile`):
- Multi-stage build: builder (pip install) → runtime (slim)
- Non-root user, health check endpoint
- Entry point: `uvicorn app.main:app`

**Frontend** (`frontend/Dockerfile`):
- Multi-stage: deps → build → production (Next.js standalone)
- Static assets served from Next.js

### Deployment Commands

```bash
# Deploy infrastructure (dev)
make azure-deploy-dev

# Build and push Docker images to ACR
make azure-build-push TAG=v1.0.0

# Deploy Container Apps with new images
make azure-deploy-apps TAG=v1.0.0

# Run migrations on Azure
make azure-migrate

# View logs
make azure-logs

# Check Azure costs
make azure-cost
```

---

## 11. CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`):

### Jobs

1. **lint** — Ruff check + format check
2. **test-backend** — 563 pytest tests (unit + integration + e2e) with Docker services
3. **test-frontend** — 117 vitest tests + ESLint + TypeScript check
4. **build** — Docker image builds for API + Frontend
5. **deploy** (main branch only) — Push to ACR + update Container Apps

### Triggers

- **Push to `main`** — Full pipeline including deploy
- **Pull requests** — Lint + test + build (no deploy)

---

## 12. Coding Standards

### Python

- **Formatter/Linter:** Ruff (configured in `pyproject.toml`)
- **Type checking:** mypy with `strict = true`
- **Line length:** 100 characters
- **Imports:** isort (via Ruff), `known-first-party = ["app"]`
- **Rules enabled:** E, W, F, I, N, UP, B, A, C4, SIM, TCH, RUF
- **Naming:** snake_case for variables/functions, PascalCase for classes
- **Docstrings:** Google-style, required on all public functions/classes
- **`from __future__ import annotations`** in every file for PEP 604 syntax

### TypeScript/React

- **Linter:** ESLint (Next.js config)
- **Type checking:** `tsc --noEmit`
- **Formatting:** Prettier (via ESLint integration)
- **Components:** Functional with explicit return types
- **Naming:** PascalCase components, camelCase functions/variables

### Git Conventions

- Branch naming: `feature/...`, `fix/...`, `chore/...`
- Commit messages: imperative mood, reference task IDs (e.g., "Implement expression parser (T501)")
- PRs require passing CI before merge

---

## 13. Troubleshooting

### Common Issues

**"Connection refused" on database/Redis/Qdrant:**
- Ensure Docker services are running: `make up`
- Check Docker logs: `make logs`

**"AZURE_OPENAI_API_KEY is required":**
- Edit `.env` and set your Azure OpenAI credentials
- If using direct OpenAI: set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`

**"SEC EDGAR User-Agent must contain an email":**
- Update `SEC_EDGAR_USER_AGENT` in `.env` with your email

**Alembic migration errors:**
- Ensure PostgreSQL is running and accessible
- Check `DATABASE_URL` in `.env`
- Run `make migrate` (or `make reset` for a clean slate)

**Frontend can't reach API:**
- Ensure `NEXT_PUBLIC_API_URL=http://localhost:8000` in frontend `.env`
- Ensure `NEXT_PUBLIC_API_KEY` matches `API_KEY` in backend `.env`
- Check CORS configuration in `main.py`

**Tests failing with timeout:**
- Default timeout is 30 seconds — increase via `--timeout=120`
- E2E tests need all Docker services running
- Integration tests need PostgreSQL, Redis, Qdrant

**Rate limiting in development:**
- Default: 100 CRUD + 20 chat requests per minute
- Increase via `API_RATE_LIMIT_CRUD` / `API_RATE_LIMIT_CHAT` in `.env`
- Redis must be running for rate limiting to function (otherwise fails open)

### Useful Debug Commands

```bash
# Check all service health
curl http://localhost:8000/api/v1/health | python -m json.tool

# Open database shell
make db-shell

# View Qdrant dashboard
open http://localhost:6333/dashboard

# Monitor Celery tasks
make flower

# Check test coverage
make test-coverage
```

---

*This guide covers the complete InvestorInsights platform as of v1.0.0. For the user-facing guide, see [user-guide.md](./user-guide.md). For deployment procedures, see [DEPLOYMENT.md](../DEPLOYMENT.md).*
