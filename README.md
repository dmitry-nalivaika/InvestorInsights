# InvestorInsights

> AI-powered SEC filing analysis platform with RAG chat, financial scoring engine, multi-company comparison, and a modern Next.js frontend.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Backend](#backend)
- [Frontend](#frontend)
- [Testing](#testing)
- [Docker](#docker)
- [Azure Deployment](#azure-deployment)
- [Configuration](#configuration)
- [API Reference](#api-reference)

---

## Overview

InvestorInsights is a full-stack platform that ingests SEC filings (10-K, 10-Q), extracts financial data via XBRL parsing, embeds document chunks for vector search, and provides:

1. **RAG Chat** — Ask questions about company filings with source-cited, streaming AI answers
2. **Analysis Engine** — Score companies against configurable criteria (25+ built-in financial formulas)
3. **Multi-Company Comparison** — Compare analysis results across multiple companies side-by-side
4. **Financial Data Browser** — View extracted metrics in a metrics×years table with CSV export

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────────┐
│   Next.js UI    │────▶│             FastAPI Backend               │
│  (React 19,     │     │  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│   TanStack Q)   │     │  │Companies │  │  Chat    │  │Analysis│ │
└─────────────────┘     │  │Documents │  │  (SSE)   │  │Scoring │ │
                        │  │Financials│  │  RAG     │  │Compare │ │
                        │  └────┬─────┘  └────┬─────┘  └───┬────┘ │
                        │       │             │             │      │
                        │  ┌────▼─────────────▼─────────────▼────┐ │
                        │  │          Service Layer               │ │
                        │  └────┬─────────────┬─────────────┬────┘ │
                        └───────┼─────────────┼─────────────┼──────┘
                                │             │             │
                  ┌─────────────▼──┐  ┌───────▼──┐  ┌──────▼──────┐
                  │  PostgreSQL    │  │  Qdrant  │  │ Azure OpenAI│
                  │  (data store)  │  │ (vectors)│  │  (LLM/embed)│
                  └────────────────┘  └──────────┘  └─────────────┘
                                │
                  ┌─────────────▼──┐  ┌───────────┐
                  │  Redis         │  │ Azure Blob│
                  │  (cache/queue) │  │ (filings) │
                  └────────────────┘  └───────────┘
```

| Layer       | Technology                                             |
|-------------|-------------------------------------------------------|
| Backend     | Python 3.12, FastAPI, SQLAlchemy (async), Celery       |
| Frontend    | Next.js 16, React 19, TypeScript, Tailwind CSS v4      |
| Database    | PostgreSQL 16, Alembic migrations                      |
| Vectors     | Qdrant                                                 |
| AI/LLM      | Azure OpenAI (gpt-4o-mini, text-embedding-3-large)    |
| Storage     | Azure Blob Storage (Azurite for local dev)             |
| Cache/Queue | Redis 7 (Celery broker + caching + rate limiting)      |
| Infra       | Azure Container Apps, Bicep IaC                        |

## Features

- **Company Management** — CRUD with SEC EDGAR CIK resolution
- **Document Ingestion** — Upload or fetch from SEC EDGAR, parse PDF/HTML, chunk, embed
- **XBRL Financial Extraction** — Automatic extraction of income statement, balance sheet, cash flow data
- **RAG Chat with Streaming** — SSE-based streaming chat with source citations
- **Analysis Scoring Engine** — 25+ financial formulas, configurable profiles, trend detection, AI summaries
- **Multi-Company Comparison** — Side-by-side scoring matrix with rankings
- **Rate Limiting** — Per-IP sliding window (100/min CRUD, 20/min chat) via Redis
- **Full Web UI** — Responsive dashboard, company detail (5 tabs), analysis profiles, comparison, settings

## Prerequisites

- **Python** 3.12+
- **Node.js** 20+
- **Docker** & Docker Compose (for local infrastructure services)
- **Azure OpenAI** API key and endpoint (or OpenAI API key)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-org/investorinsights.git
cd investorinsights
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

### 2. One-command setup

```bash
make setup
```

This will:
- Create a Python virtual environment
- Install backend + dev dependencies
- Start Docker services (PostgreSQL, Redis, Qdrant, Azurite)
- Run database migrations

### 3. Start the backend

```bash
make dev
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:3000
```

### 5. Seed default data

```bash
make seed
```

### 6. Run tests

```bash
# Backend tests
make test

# Frontend tests
cd frontend && npm test
```

## Project Structure

```
investorinsights/
├── backend/                    # FastAPI API server + Celery workers
│   ├── app/
│   │   ├── main.py            # App factory, middleware wiring
│   │   ├── config.py          # Pydantic BaseSettings config
│   │   ├── dependencies.py    # FastAPI DI (DB session, settings, storage)
│   │   ├── api/               # Route handlers
│   │   │   ├── companies.py   # Company CRUD
│   │   │   ├── documents.py   # Document management
│   │   │   ├── financials.py  # Financial data endpoints
│   │   │   ├── chat.py        # SSE streaming chat
│   │   │   ├── analysis.py    # Analysis + comparison endpoints
│   │   │   └── middleware/     # Auth, rate limiter, request ID, errors
│   │   ├── analysis/          # Scoring engine, formulas, trend detection
│   │   ├── clients/           # External clients (OpenAI, Qdrant, Redis, etc.)
│   │   ├── db/                # SQLAlchemy session + repositories
│   │   ├── ingestion/         # Document parsing, chunking, embedding
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── rag/               # RAG chat agent
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic layer
│   │   └── worker/            # Celery task definitions
│   ├── alembic/               # Database migrations
│   ├── tests/                 # Backend test suite
│   ├── Dockerfile             # Multi-stage production image
│   └── requirements.txt
├── frontend/                   # Next.js web application
│   ├── src/
│   │   ├── app/               # App Router pages
│   │   ├── components/        # Reusable UI components
│   │   ├── lib/               # API client, SSE client, format utils
│   │   └── providers/         # TanStack Query provider
│   ├── tests/                 # Frontend tests (Vitest + RTL)
│   ├── Dockerfile             # Multi-stage standalone image
│   └── package.json
├── infra/                      # Azure Bicep IaC
│   ├── main.bicep
│   ├── modules/               # Individual resource modules
│   └── parameters/            # Dev and prod parameter files
├── docker-compose.dev.yml      # Local infrastructure services
├── Makefile                    # Common development commands
└── specs/                      # Feature specifications
```

## Backend

### Key APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/companies` | GET/POST | List/create companies |
| `/api/v1/companies/{id}` | GET/PUT/DELETE | Company CRUD |
| `/api/v1/companies/{id}/documents` | GET/POST | Document management |
| `/api/v1/companies/{id}/financials` | GET | Financial data (metrics×years) |
| `/api/v1/companies/{id}/chat` | POST | Streaming chat (SSE) |
| `/api/v1/analysis/profiles` | GET/POST | Analysis profile management |
| `/api/v1/analysis/run` | POST | Run analysis on companies |
| `/api/v1/analysis/compare` | POST | Compare multiple companies |
| `/api/v1/health` | GET | Health check (no auth) |

### Analysis Engine

The scoring engine evaluates companies against configurable profiles with weighted criteria:

- **25+ built-in formulas**: Revenue Growth, Gross Margin, ROE, Current Ratio, Debt-to-Equity, Free Cash Flow Yield, etc.
- **Expression parser**: Custom formulas via `field1 / field2` syntax
- **Trend detection**: Identifies improving, declining, or stable trends
- **Grading**: A/B/C/D/F grades based on percentage score thresholds

### Rate Limiting

Per-IP sliding window enforced via Redis middleware:
- **CRUD endpoints**: 100 requests/minute
- **Chat endpoints**: 20 requests/minute
- **Fail-open**: If Redis is unavailable, requests are allowed
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Frontend

Built with Next.js 16 (App Router), React 19, TypeScript, and Tailwind CSS v4.

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/dashboard` | Company grid with summary cards |
| Companies | `/companies` | Searchable company table + add modal |
| Company Detail | `/companies/[id]` | 5-tab view (Overview, Documents, Financials, Chat, Analysis) |
| Analysis Profiles | `/analysis/profiles` | Profile management |
| Compare | `/analysis/compare` | Multi-company comparison matrix |
| Settings | `/settings` | Read-only config display |

**UI Features:** Responsive design (collapsible sidebar), SSE streaming chat, loading/error/empty states, compact number formatting ($394.3B).

## Testing

### Backend (pytest)

```bash
make test              # All tests
make test-unit         # Unit tests only (131+)
make test-integration  # Integration tests only (33+)
make test-coverage     # With coverage report
```

### Frontend (Vitest + RTL)

```bash
cd frontend
npm test               # All tests (117+)
npm run test:watch     # Watch mode
```

## Docker

### Build images

```bash
# Backend (Python 3.12-slim, multi-stage, non-root)
docker build -t investorinsights-api ./backend

# Frontend (Node 20-alpine, standalone, non-root)
docker build -t investorinsights-frontend ./frontend
```

### Local infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d    # Start PG, Redis, Qdrant, Azurite
docker compose -f docker-compose.dev.yml down      # Stop
```

## Azure Deployment

```bash
make azure-deploy-dev          # Deploy Bicep infrastructure
make azure-seed-keyvault       # Populate secrets
make azure-build-push          # Build & push images to ACR
make azure-deploy-apps         # Deploy Container Apps
make azure-migrate             # Run DB migrations
```

**Dev budget target: ≤ $50/month** — see `docs/runbooks/budget-breach.md` for scale-down procedures.

## Configuration

All config via environment variables (`.env` locally, Key Vault in production).

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (required) | API authentication key |
| `AZURE_OPENAI_API_KEY` | (required) | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | (required) | Azure OpenAI endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model |
| `CHUNK_SIZE` | `768` | Document chunk size (tokens) |
| `RAG_TOP_K` | `15` | Chunks retrieved per query |
| `RAG_SCORE_THRESHOLD` | `0.65` | Minimum similarity score |
| `API_RATE_LIMIT_CRUD` | `100` | CRUD rate limit (req/min) |
| `API_RATE_LIMIT_CHAT` | `20` | Chat rate limit (req/min) |

## API Reference

Interactive API documentation available in development:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

See [specs/001-investorinsights-platform/](specs/001-investorinsights-platform/README.md) for full specification.
