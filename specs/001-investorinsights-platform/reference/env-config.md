# Environment Configuration Reference

> Referenced from [Plan](../plan.md)

In Azure deployment, secrets (marked with 🔒) are stored in **Azure Key Vault** and
injected into Container Apps via managed identity secret references. Non-secret
configuration is set directly on Container App environment variables.

For **local development**, a `.env` file is used with Docker Compose.

---

```bash
# ================================================================
# .env.example — Local development configuration
# In Azure: secrets come from Key Vault, config from Container App settings
# ================================================================

# ── Application ──────────────────────────────────────────────────
APP_NAME=investorinsights
APP_VERSION=1.0.0
APP_ENV=development                     # development | staging | production
LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
API_KEY=your-secret-api-key-here        # 🔒 Key Vault in Azure

# ── Database (Azure Database for PostgreSQL Flexible Server) ─────
DB_HOST=localhost                        # Azure: {server}.postgres.database.azure.com
DB_PORT=5432
DB_NAME=company_analysis
DB_USER=analyst                          # Azure: {admin}@{server}
DB_PASSWORD=change-this-in-production    # 🔒 Key Vault in Azure
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_SSL_MODE=prefer                      # Azure: require

# ── Vector Store (Qdrant — on Container Apps in Azure) ───────────
QDRANT_HOST=localhost                    # Azure: internal Container App FQDN
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_URL=http://${QDRANT_HOST}:${QDRANT_HTTP_PORT}
QDRANT_API_KEY=                         # 🔒 Key Vault (optional)
QDRANT_COLLECTION_PREFIX=company_

# ── Object Storage (Azure Blob Storage) ──────────────────────────
AZURE_STORAGE_CONNECTION_STRING=        # 🔒 Key Vault in Azure
AZURE_STORAGE_ACCOUNT_NAME=
AZURE_STORAGE_CONTAINER_FILINGS=filings
AZURE_STORAGE_CONTAINER_EXPORTS=exports
# Local dev (Azurite):
# AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;...

# ── Redis (Container App in dev / Azure Cache for Redis in prod) ──
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=                         # 🔒 Key Vault (prod only)
REDIS_SSL=false                         # Azure prod: true
REDIS_MAX_CONNECTIONS=20

# ── Celery Workers ───────────────────────────────────────────────
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
WORKER_CONCURRENCY=4
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_SOFT_TIME_LIMIT=540

# ── Azure OpenAI (primary LLM provider) ─────────────────────────
LLM_PROVIDER=azure_openai               # azure_openai | openai | anthropic
AZURE_OPENAI_API_KEY=                    # 🔒 Key Vault
AZURE_OPENAI_ENDPOINT=https://{name}.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini # dev: gpt-4o-mini, prod: gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# ── OpenAI Direct (optional fallback) ────────────────────────────
# OPENAI_API_KEY=sk-your-openai-key-here  # 🔒 Key Vault

# ── LLM Configuration ───────────────────────────────────────────
LLM_MODEL=gpt-4o-mini                   # dev: gpt-4o-mini; prod: gpt-4o
LLM_FALLBACK_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=120
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
EMBEDDING_BATCH_SIZE=64

# ── RAG Configuration ───────────────────────────────────────────
RAG_TOP_K=15
RAG_SCORE_THRESHOLD=0.65
RAG_MAX_CONTEXT_TOKENS=12000
RAG_MAX_HISTORY_TOKENS=4000
RAG_MAX_HISTORY_EXCHANGES=10

# ── Ingestion Configuration ──────────────────────────────────────
CHUNK_SIZE=768
CHUNK_OVERLAP=128
MAX_UPLOAD_SIZE_MB=50

# ── SEC EDGAR ────────────────────────────────────────────────────
SEC_EDGAR_USER_AGENT=InvestorInsights/1.0 (your-email@example.com)
SEC_EDGAR_RATE_LIMIT=10
SEC_EDGAR_BASE_URL=https://data.sec.gov

# ── API Server ───────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RATE_LIMIT_CRUD=100
API_RATE_LIMIT_CHAT=20

# ── Azure Monitor / Application Insights ─────────────────────────
APPLICATIONINSIGHTS_CONNECTION_STRING=
OTEL_SERVICE_NAME=investorinsights-api

# ── Frontend ─────────────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=InvestorInsights

# ── Local Dev Ports ──────────────────────────────────────────────
FRONTEND_PORT=3000
API_EXTERNAL_PORT=8000
DB_EXTERNAL_PORT=5432
QDRANT_EXTERNAL_HTTP_PORT=6333
QDRANT_EXTERNAL_GRPC_PORT=6334
REDIS_EXTERNAL_PORT=6379
```

---

## Configuration Validation

On startup, Pydantic `BaseSettings` validates all required configuration:

1. All required env vars present
2. `DATABASE_URL` is valid connection string
3. `LLM_PROVIDER` is one of: `azure_openai`, `openai`, `anthropic`
4. If `azure_openai`: `AZURE_OPENAI_ENDPOINT` and deployment names present
5. If `openai`: `OPENAI_API_KEY` starts with `sk-`
6. `SEC_EDGAR_USER_AGENT` contains email address
7. Numeric ranges valid (CHUNK_SIZE > 0, etc.)
8. Connectivity check: ping DB, Redis, Qdrant, Azure Blob on startup
9. If Azure: validate managed identity can access Key Vault
