# InvestorInsights

> AI-powered SEC filing analysis platform with RAG chat, financial analysis engine, and Next.js frontend.

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start local services
make setup
make up

# 3. Run tests
make test
```

## Architecture

- **Backend**: Python 3.12+ / FastAPI / SQLAlchemy / Celery
- **Frontend**: Next.js 14+ / TypeScript / shadcn/ui / Tailwind CSS
- **Data**: PostgreSQL / Qdrant (vectors) / Azure Blob Storage / Redis
- **AI**: Azure OpenAI (gpt-4o / gpt-4o-mini, text-embedding-3-large)
- **Infra**: Azure Container Apps / Bicep IaC

## Project Structure

```
├── backend/          # FastAPI API + Celery workers
├── frontend/         # Next.js web application
├── infra/            # Azure Bicep IaC
├── scripts/          # Development utilities
├── specs/            # Feature specifications
└── docs/             # Operational runbooks
```

See [specs/001-investorinsights-platform/](specs/001-investorinsights-platform/README.md) for full specification.
