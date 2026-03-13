# InvestorInsights Constitution

## Core Principles

### I. Company-Scoped Data Model

All data, chat, and analysis is organized per-company. The company is the central entity.
Every document, financial record, chat session, analysis result, and vector collection
belongs to exactly one company. Cross-company operations (comparisons) are explicit
join queries, never implicit.

### II. Grounded AI — No Speculation

The AI chat agent must ONLY answer based on uploaded SEC filings. It must cite sources
(filing type, fiscal year, section). It must refuse to speculate beyond the data, predict
future performance, recommend buy/sell actions, or fabricate financial numbers. If the
answer is not in the filings, the agent says so.

### III. User-Defined Criteria

The financial scoring system is fully configurable. Users define what to measure
(formula), how to compute it (built-in or custom expression), what thresholds to apply
(comparison + value), and how to weight each criterion. The system never hard-codes
investment philosophy — it evaluates whatever the user configures.

### IV. Azure Cloud-Native

The platform runs on Azure using managed services: Azure Container Apps, Azure Database
for PostgreSQL, Azure Blob Storage, Azure OpenAI, Azure Key Vault, Azure Monitor.
Infrastructure is provisioned via Bicep IaC with per-environment parameter files.
Development environment is budget-optimised (≤ $50/month) with scale-to-zero, smallest
DB SKU, containerised Redis, and no VNet. Production adds managed Redis, VNet with
private endpoints, and larger SKUs.

### V. Single User (V1) — Simplicity First

V1 is designed for a single analyst. Authentication is API key. Multi-user and Azure
AD/Entra ID are V2 considerations. Prefer simplicity over cleverness, explicit over
implicit. Start simple, YAGNI principles. When in doubt, do the simpler thing.

### VI. Offline-Capable Data

Once filings are ingested, all analysis and chat works without re-fetching from SEC.
Only LLM inference requires Azure OpenAI API calls. Raw files are preserved in Blob
Storage even if ingestion fails, ensuring no data loss.

### VII. Observability

Structured logging (structlog + JSON) exported via OpenTelemetry to Azure Monitor /
Application Insights. Custom metrics for ingestion throughput, LLM token usage, analysis
duration. All operations carry a `request_id` for distributed tracing. No sensitive data
(API keys, file contents, full chat messages) in logs.

## Technology Governance

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0+, Celery, Pydantic 2
- **Frontend**: Next.js 14+, TypeScript, shadcn/ui, Tailwind CSS, React Query
- **Data**: Azure DB for PostgreSQL (PG 16), Qdrant (vector), Azure Blob Storage, Redis
- **AI**: Azure OpenAI (gpt-4o / gpt-4o-mini, text-embedding-3-large)
- **IaC**: Bicep modules in `infra/`
- **Testing**: pytest + pytest-asyncio (backend), Vitest + RTL (frontend)
- **Linting**: Ruff + mypy (Python), ESLint + Prettier (TypeScript)
- **Migrations**: Alembic (versioned, never destructive in prod)

## Governance

- Specification version: 3.0.0
- Any deviation from this constitution must be documented with rationale
- Budget constraint (dev ≤ $50/month) overrides feature richness in development
- SEC EDGAR rate limits (10 req/s) are a hard constraint — never bypass
- LLM prompt security: user input never appears in system prompt
