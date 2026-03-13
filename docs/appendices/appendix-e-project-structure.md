# Appendix E: Project Directory Structure

> Referenced from [System Specification](../system_specification.md)

```
company-analysis-platform/
├── README.md
├── DEPLOYMENT.md                         # Azure deployment guide
├── LICENSE
├── docker-compose.dev.yml                # local development (PostgreSQL, Redis, Qdrant, Azurite)
├── docker-compose.override.yml           # dev overrides (volume mounts)
├── .env.example
├── .gitignore
├── Makefile                              # common commands (see Appendix F)
│
├── infra/                                # Azure Infrastructure as Code (Bicep)
│   ├── main.bicep                        # orchestrator — deploys all modules
│   ├── main.bicepparam
│   ├── parameters/
│   │   ├── dev.bicepparam
│   │   └── prod.bicepparam
│   ├── modules/
│   │   ├── resource-group.bicep
│   │   ├── networking.bicep              # VNet, subnets, private endpoints
│   │   ├── postgresql.bicep              # Azure DB for PostgreSQL Flex Server
│   │   ├── redis.bicep                   # Azure Cache for Redis
│   │   ├── storage.bicep                 # Azure Blob Storage + containers
│   │   ├── openai.bicep                  # Azure OpenAI + model deployments
│   │   ├── key-vault.bicep               # Azure Key Vault + secrets
│   │   ├── container-registry.bicep      # Azure Container Registry
│   │   ├── log-analytics.bicep           # Log Analytics workspace
│   │   ├── app-insights.bicep            # Application Insights
│   │   └── container-apps.bicep          # Container Apps Environment + apps
│   ├── dashboards/
│   │   ├── api-performance.json          # Azure Portal dashboard template
│   │   ├── ingestion-pipeline.json
│   │   └── llm-usage.json
│   └── scripts/
│       ├── deploy.sh                     # az deployment sub create wrapper
│       ├── destroy.sh                    # tear down environment
│       └── seed-keyvault.sh              # initial secret population
│
├── .github/
│   └── workflows/
│       ├── ci.yml                        # lint, test, build on PRs
│       ├── deploy-staging.yml            # deploy to staging on merge to main
│       └── deploy-prod.yml              # deploy to prod (manual trigger)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt              # test + dev dependencies
│   ├── pyproject.toml                    # ruff, mypy, pytest config
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── ...
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app factory
│   │   ├── config.py                     # Pydantic Settings
│   │   ├── dependencies.py               # FastAPI dependency injection
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py                 # top-level router (includes all sub-routers)
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py               # API key authentication
│   │   │   │   ├── error_handler.py      # global error handling
│   │   │   │   ├── logging.py            # request logging
│   │   │   │   └── rate_limit.py         # rate limiting
│   │   │   ├── companies.py              # company endpoints
│   │   │   ├── documents.py              # document endpoints
│   │   │   ├── chat.py                   # chat endpoints (SSE)
│   │   │   ├── analysis.py               # analysis endpoints
│   │   │   ├── financials.py             # financial data endpoints
│   │   │   ├── health.py                 # health check endpoint
│   │   │   └── tasks.py                  # async task status endpoint
│   │   │
│   │   ├── models/                       # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # declarative base, mixins
│   │   │   ├── company.py
│   │   │   ├── document.py
│   │   │   ├── section.py
│   │   │   ├── chunk.py
│   │   │   ├── financial.py
│   │   │   ├── profile.py
│   │   │   ├── criterion.py
│   │   │   ├── result.py
│   │   │   ├── session.py
│   │   │   └── message.py
│   │   │
│   │   ├── schemas/                      # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── company.py                # CompanyCreate, CompanyRead, CompanyList
│   │   │   ├── document.py               # DocumentUpload, DocumentRead, DocumentStatus
│   │   │   ├── chat.py                   # ChatRequest, ChatMessage, SessionRead
│   │   │   ├── analysis.py               # ProfileCreate, CriterionDef, AnalysisResult
│   │   │   ├── financial.py              # FinancialPeriod, FinancialExport
│   │   │   └── common.py                 # PaginatedResponse, ErrorResponse
│   │   │
│   │   ├── services/                     # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── company_service.py
│   │   │   ├── document_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── analysis_service.py
│   │   │   └── financial_service.py
│   │   │
│   │   ├── ingestion/                    # Document processing pipeline
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py               # orchestrator
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── html_parser.py
│   │   │   │   └── text_cleaner.py
│   │   │   ├── section_splitter.py
│   │   │   ├── chunker.py
│   │   │   └── embedding_service.py
│   │   │
│   │   ├── analysis/                     # Financial analysis engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                 # main analysis orchestrator
│   │   │   ├── formula_registry.py       # built-in formula definitions
│   │   │   ├── formula_parser.py         # custom expression parser
│   │   │   ├── threshold_evaluator.py
│   │   │   ├── trend_detector.py
│   │   │   └── scorer.py
│   │   │
│   │   ├── rag/                          # RAG chat agent
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                  # CompanyChatAgent
│   │   │   ├── retriever.py              # vector search + filtering
│   │   │   ├── prompt_builder.py         # system prompt + context assembly
│   │   │   └── query_expander.py         # optional query expansion
│   │   │
│   │   ├── clients/                      # External service clients
│   │   │   ├── __init__.py
│   │   │   ├── openai_client.py          # embeddings + chat (Azure OpenAI + direct OpenAI)
│   │   │   ├── sec_edgar_client.py       # EDGAR API interactions
│   │   │   ├── qdrant_client.py          # vector DB operations
│   │   │   └── storage_client.py         # Azure Blob Storage operations
│   │   │
│   │   ├── db/                           # Database utilities
│   │   │   ├── __init__.py
│   │   │   ├── session.py                # async session factory
│   │   │   └── repositories/             # data access layer
│   │   │       ├── __init__.py
│   │   │       ├── company_repo.py
│   │   │       ├── document_repo.py
│   │   │       ├── financial_repo.py
│   │   │       ├── profile_repo.py
│   │   │       ├── result_repo.py
│   │   │       └── chat_repo.py
│   │   │
│   │   ├── worker/                       # Celery worker
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py             # Celery configuration
│   │   │   ├── tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ingestion_tasks.py
│   │   │   │   ├── analysis_tasks.py
│   │   │   │   └── sec_fetch_tasks.py
│   │   │   └── callbacks.py              # task success/failure handlers
│   │   │
│   │   └── xbrl/                         # XBRL processing
│   │       ├── __init__.py
│   │       ├── mapper.py                 # XBRL tag → internal schema mapping
│   │       ├── tag_registry.py           # known XBRL tags and alternatives
│   │       └── period_selector.py        # select correct period from facts
│   │
│   └── tests/
│       ├── conftest.py                   # shared fixtures
│       ├── factories.py                  # test data factories
│       │
│       ├── unit/
│       │   ├── test_section_splitter.py
│       │   ├── test_chunker.py
│       │   ├── test_formulas.py
│       │   ├── test_formula_parser.py
│       │   ├── test_trend_detection.py
│       │   ├── test_threshold_evaluator.py
│       │   ├── test_scoring.py
│       │   ├── test_document_parser.py
│       │   ├── test_xbrl_mapper.py
│       │   ├── test_sec_client.py
│       │   ├── test_prompt_builder.py
│       │   └── test_text_cleaner.py
│       │
│       ├── integration/
│       │   ├── conftest.py               # testcontainers setup
│       │   ├── test_company_api.py
│       │   ├── test_document_api.py
│       │   ├── test_ingestion_pipeline.py
│       │   ├── test_chat_api.py
│       │   ├── test_analysis_api.py
│       │   ├── test_financials_api.py
│       │   ├── test_auth.py
│       │   └── test_health.py
│       │
│       ├── e2e/
│       │   ├── conftest.py
│       │   ├── test_company_journey.py
│       │   ├── test_upload_chat_journey.py
│       │   ├── test_analysis_journey.py
│       │   └── test_comparison_journey.py
│       │
│       ├── performance/
│       │   ├── locustfile.py
│       │   └── test_vector_search_perf.py
│       │
│       └── fixtures/
│           ├── generate_fixtures.py
│           ├── simple_10k.pdf
│           ├── simple_10k.html
│           ├── corrupt_file.pdf
│           ├── companyfacts_complete.json
│           ├── companyfacts_sparse.json
│           ├── test_financials_5y.json
│           ├── chat_response_risk_factors.json
│           ├── analysis_summary_response.json
│           ├── test_embeddings.npy
│           ├── edgar_company_tickers.json
│           └── edgar_submissions.json
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── .eslintrc.json
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── logo.svg
│   │
│   ├── src/
│   │   ├── app/                          # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                  # → /dashboard
│   │   │   ├── companies/
│   │   │   │   ├── page.tsx              # company list
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx          # company detail (tabs)
│   │   │   │       └── layout.tsx
│   │   │   ├── analysis/
│   │   │   │   ├── profiles/
│   │   │   │   │   ├── page.tsx
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx      # profile editor
│   │   │   │   └── compare/
│   │   │   │       └── page.tsx
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                       # shadcn/ui components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── table.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── select.tsx
│   │   │   │   ├── textarea.tsx
│   │   │   │   ├── slider.tsx
│   │   │   │   ├── tooltip.tsx
│   │   │   │   ├── accordion.tsx
│   │   │   │   ├── skeleton.tsx
│   │   │   │   ├── toast.tsx
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── header.tsx
│   │   │   │   └── main-layout.tsx
│   │   │   │
│   │   │   ├── company/
│   │   │   │   ├── company-card.tsx
│   │   │   │   ├── company-grid.tsx
│   │   │   │   ├── company-header.tsx
│   │   │   │   ├── add-company-modal.tsx
│   │   │   │   └── company-tabs.tsx
│   │   │   │
│   │   │   ├── documents/
│   │   │   │   ├── document-table.tsx
│   │   │   │   ├── document-timeline.tsx
│   │   │   │   ├── upload-modal.tsx
│   │   │   │   ├── fetch-sec-modal.tsx
│   │   │   │   └── status-badge.tsx
│   │   │   │
│   │   │   ├── chat/
│   │   │   │   ├── chat-interface.tsx
│   │   │   │   ├── message-list.tsx
│   │   │   │   ├── message-bubble.tsx
│   │   │   │   ├── chat-input.tsx
│   │   │   │   ├── session-list.tsx
│   │   │   │   ├── source-panel.tsx
│   │   │   │   ├── source-chip.tsx
│   │   │   │   └── typing-indicator.tsx
│   │   │   │
│   │   │   ├── analysis/
│   │   │   │   ├── profile-editor.tsx
│   │   │   │   ├── criteria-builder.tsx
│   │   │   │   ├── formula-selector.tsx
│   │   │   │   ├── score-card.tsx
│   │   │   │   ├── criteria-table.tsx
│   │   │   │   ├── trend-chart.tsx
│   │   │   │   ├── comparison-table.tsx
│   │   │   │   └── ai-summary.tsx
│   │   │   │
│   │   │   ├── financials/
│   │   │   │   ├── financial-table.tsx
│   │   │   │   ├── metric-chart.tsx
│   │   │   │   └── period-selector.tsx
│   │   │   │
│   │   │   └── common/
│   │   │       ├── loading-spinner.tsx
│   │   │       ├── error-display.tsx
│   │   │       ├── empty-state.tsx
│   │   │       ├── confirm-dialog.tsx
│   │   │       └── number-format.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── use-companies.ts          # React Query hooks
│   │   │   ├── use-documents.ts
│   │   │   ├── use-chat.ts
│   │   │   ├── use-analysis.ts
│   │   │   ├── use-financials.ts
│   │   │   ├── use-sse.ts                # SSE stream hook
│   │   │   └── use-debounce.ts
│   │   │
│   │   ├── lib/
│   │   │   ├── api-client.ts             # configured HTTP client
│   │   │   ├── sse-client.ts             # SSE stream parser
│   │   │   ├── formatters.ts             # number/date formatting
│   │   │   ├── constants.ts
│   │   │   ├── types.ts                  # TypeScript types matching API schemas
│   │   │   └── utils.ts                  # cn() helper, etc.
│   │   │
│   │   └── providers/
│   │       ├── query-provider.tsx        # React Query provider
│   │       └── theme-provider.tsx
│   │
│   └── tests/
│       ├── components/
│       │   ├── company-card.test.tsx
│       │   ├── chat-interface.test.tsx
│       │   ├── score-card.test.tsx
│       │   └── ...
│       └── hooks/
│           ├── use-companies.test.ts
│           └── use-sse.test.ts
│
└── scripts/
    ├── setup.sh                          # first-time local dev setup (create .env, init DB)
    ├── seed.sh                           # seed default analysis profile
    └── reset.sh                          # wipe all local data (development)
```
