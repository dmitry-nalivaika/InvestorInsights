# Research: InvestorInsights Platform

**Spec**: [spec.md](./spec.md)

---

## Key Technical Decisions

### 1. Azure Cloud vs. Self-Hosted

**Decision**: Azure managed services

**Rationale**: The platform targets a single developer/analyst. Self-hosted Docker Compose
requires maintaining VMs, patching OS, managing backups manually. Azure managed services
(PostgreSQL Flex, Blob Storage, Key Vault, Container Apps) offload operational burden.
The Consumption plan for Container Apps with scale-to-zero keeps dev costs under $50/month.

**Trade-offs**:
- (+) No server management, automatic backups, SLA guarantees in prod
- (+) Budget-optimised dev environment (~$22–34/month)
- (-) Azure lock-in for storage, secrets, monitoring APIs
- (-) Cold starts with scale-to-zero (~5s for first request)

### 2. Qdrant on Container Apps vs. pgvector

**Decision**: Qdrant as a dedicated Container App

**Rationale**: pgvector would reduce infrastructure by keeping vectors in PostgreSQL, but
Qdrant provides better performance for filtered similarity search (metadata filters on
doc_type, fiscal_year, section_key), native per-collection isolation (one collection per
company), and purpose-built HNSW indexing. At 500K+ vectors per company, Qdrant's query
latency is significantly better. It runs as a Container App with persistent Azure Files
volume, costing effectively $0 in dev (scale-to-zero).

**Trade-offs**:
- (+) Sub-200ms filtered search at scale
- (+) Per-company collection isolation (easy to delete all vectors for a company)
- (+) Payload storage on disk (large chunk texts)
- (-) Additional container to manage
- (-) Snapshot-based backup (not PITR like PostgreSQL)

### 3. Celery + Redis vs. Azure Queue Storage

**Decision**: Celery + Redis (containerised in dev, Azure Cache in prod)

**Rationale**: Celery provides mature task management with retries, dead-letter handling,
concurrency control, and monitoring (Flower). Azure Queue Storage would reduce
infrastructure but lacks Celery's task orchestration features. In dev, Redis runs as a
Container App at zero cost. In prod, Azure Cache for Redis provides managed HA.

### 4. gpt-4o-mini (dev) vs. gpt-4o (prod)

**Decision**: Environment-specific model selection

**Rationale**: gpt-4o-mini is ~10× cheaper per token ($0.15/$0.60 per 1M input/output)
vs. gpt-4o ($2.50/$10.00). For development and testing, gpt-4o-mini provides sufficient
quality. Production uses gpt-4o for better reasoning. Both are configured via environment
variables (`AZURE_OPENAI_CHAT_DEPLOYMENT`).

### 5. text-embedding-3-large (3072 dims) vs. text-embedding-3-small (1536 dims)

**Decision**: text-embedding-3-large

**Rationale**: SEC filings contain dense technical and financial language. The larger
embedding model provides better semantic discrimination for domain-specific queries.
Storage cost difference is negligible in Qdrant at our scale (<5M vectors total).

### 6. XBRL API vs. PDF Parsing for Financial Data

**Decision**: SEC EDGAR XBRL `companyfacts` API as primary source

**Rationale**: The companyfacts endpoint returns ALL historical XBRL-tagged financial
data for a company in a single API call. This is vastly more reliable than trying to
parse financial tables from PDF/HTML. 60+ US-GAAP tags are mapped to the internal schema.
PDF parsing is used only for text content (qualitative analysis), not numbers.

### 7. FastAPI + SQLAlchemy vs. Django

**Decision**: FastAPI + SQLAlchemy 2.0 async

**Rationale**: FastAPI provides native async support critical for SSE streaming, parallel
LLM/vector queries, and non-blocking I/O. Auto-generated OpenAPI docs. Pydantic v2 for
request/response validation. SQLAlchemy 2.0 async provides the ORM layer. Django would
add unnecessary overhead for this API-first application with no admin panel needs.

### 8. Next.js vs. Vite + React

**Decision**: Next.js 14+ with App Router

**Rationale**: SSR capabilities for initial page load performance, built-in routing,
API routes for BFF pattern if needed. shadcn/ui provides a complete component library
with Tailwind CSS integration. The framework is well-suited for the dashboard-style UI.

### 9. No VNet in Dev

**Decision**: Public endpoints + firewall rules for development

**Rationale**: Azure VNet + private endpoints add ~$40/month (NAT gateway, private DNS
zones, private endpoint charges). For a single-developer non-production environment,
public endpoints with IP-based firewall rules and managed identity authentication
provide adequate security. Production uses full VNet isolation.

### 10. Expression Parser (Custom DSL) vs. Python eval()

**Decision**: Custom recursive descent parser

**Rationale**: Python `eval()` is a critical security vulnerability. A custom parser
validates field references against known financial data fields, handles `prev()` lookback
references safely, and provides clear error messages. The grammar is simple: arithmetic
operators, parentheses, `abs()/min()/max()` functions, and field references.

---

## Alternatives Considered

| Decision | Alternative | Why Rejected |
|----------|------------|--------------|
| Azure | AWS / GCP | Team familiarity with Azure; existing subscription |
| Qdrant | Pinecone | Cost; Pinecone managed pricing scales poorly for dev |
| Qdrant | Weaviate | Qdrant is simpler for our use case; better Python SDK |
| Qdrant | pgvector | Inadequate filtered search performance at scale |
| Celery | Azure Queue + Functions | Lacks task orchestration, retry policies, monitoring |
| Redis | RabbitMQ | Redis serves dual purpose (broker + cache); simpler stack |
| FastAPI | Django REST | Async SSE streaming not well supported; excess overhead |
| PyMuPDF | pdfplumber | PyMuPDF is faster for large documents |
| Next.js | Remix | Smaller ecosystem; less component library support |
| Bicep | Terraform | Azure-native, no state file management needed |

---

## SEC EDGAR Integration Notes

- **Rate limit**: Max 10 requests/second (hard requirement, enforced by SEC)
- **User-Agent**: Must include email address (SEC policy)
- **companyfacts API**: Returns complete XBRL data for a company in one call
- **Filing index**: `submissions` endpoint provides filing metadata
- **No authentication required**: Public API, free access
- **Data freshness**: XBRL data is typically available within 24 hours of filing

## Azure OpenAI Notes

- **Deployment names** are separate from model names; both must be configured
- **Rate limits**: Measured in TPM (tokens per minute); configure via capacity units
- **Region**: eastus2 recommended for model availability
- **Managed Identity**: Preferred auth method for Azure-to-Azure communication
- **Fallback**: Direct OpenAI API can be used as fallback if Azure OpenAI is unavailable
