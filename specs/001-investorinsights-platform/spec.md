# Feature Specification: InvestorInsights Platform

**Feature Branch**: `001-investorinsights-platform`
**Created**: 2025-01-XX
**Status**: Draft
**Input**: AI-powered public company analysis platform that stores/indexes SEC filings, provides a RAG chat agent per company, and automates quantitative financial analysis with user-defined scoring criteria. Deployed on Azure Cloud.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register & Browse Companies (Priority: P1)

As an analyst, I want to register a company by ticker symbol and see it in my tracked company list so I can begin uploading and analyzing its filings.

**Why this priority**: The company is the central entity. Nothing else works without it.

**Independent Test**: Register "AAPL" → company appears in list with auto-resolved name, CIK, sector.

**Acceptance Scenarios**:

1. **Given** the system has no companies, **When** I register ticker "AAPL", **Then** a company record is created with name "Apple Inc", CIK "0000320193", sector, and industry auto-populated from SEC EDGAR.
2. **Given** "AAPL" is already registered, **When** I try to register "AAPL" again, **Then** I receive a duplicate error.
3. **Given** multiple companies exist, **When** I view the company list, **Then** each company shows ticker, name, sector, document count, latest filing date, and they are sortable/searchable.
4. **Given** a company exists, **When** I view its detail page, **Then** I see a summary of filings, financial data availability, and links to chat/analysis.
5. **Given** a company exists, **When** I delete it with confirmation, **Then** the company and ALL associated data (documents, chunks, financials, chats, results) are removed.

---

### User Story 2 - Upload & Ingest SEC Filings (Priority: P1)

As an analyst, I want to upload SEC filings (PDF/HTML) or auto-fetch them from EDGAR so the system can parse, chunk, embed, and extract financial data — making them available for chat and analysis.

**Why this priority**: Ingested filings are the foundation for both chat (RAG) and analysis (XBRL data). Without documents, the platform has no value.

**Independent Test**: Upload a 10-K PDF → status progresses through uploaded → parsing → embedding → ready. Chunks appear in vector store. Financial data extracted via XBRL.

**Acceptance Scenarios**:

1. **Given** a company exists, **When** I upload a 10-K PDF with filing metadata, **Then** the file is stored, queued for processing, and I receive immediate acknowledgement with a document ID.
2. **Given** a document is uploaded, **When** processing completes, **Then** its status progresses through `uploaded → parsing → parsed → embedding → ready`.
3. **Given** a company with a CIK, **When** I trigger auto-fetch for the last 10 years, **Then** the system downloads all 10-K/10-Q filings from EDGAR, respecting rate limits, skipping duplicates.
4. **Given** a document in "error" status, **When** I retry ingestion, **Then** it resumes the pipeline from the failed stage, not from scratch.
5. **Given** a document in "ready" status, **When** I delete it, **Then** the file, all chunks from vector DB, section records, and associated financial data are removed.
6. **Given** an upload for a period that already exists, **When** submitted, **Then** I receive a 409 duplicate error.
7. **Given** a corrupt PDF, **When** processing runs, **Then** it fails gracefully with a clear error message and the status is "error".

---

### User Story 3 - Chat with AI About Company Filings (Priority: P1)

As an analyst, I want to start a chat session scoped to a specific company and ask qualitative questions about its SEC filings, receiving answers grounded in the actual documents with source citations.

**Why this priority**: The RAG chat agent is the primary differentiator — conversational access to 10+ years of filings.

**Independent Test**: Ask "What are the main risk factors?" → receive a streaming response citing specific filings, with source chunks displayed.

**Acceptance Scenarios**:

1. **Given** a company with ready filings, **When** I start a new chat and ask a question, **Then** the agent retrieves relevant chunks via semantic search, constructs a grounded prompt, and streams the response token-by-token via SSE.
2. **Given** a chat response, **When** I review it, **Then** each answer references specific filings (e.g., "According to the FY2023 10-K, Item 1A…") and I can see the source chunks with relevance scores.
3. **Given** a question that cannot be answered from the filings, **When** asked, **Then** the agent explicitly states the information is not available and does not fabricate an answer.
4. **Given** a question about future predictions or buy/sell recommendations, **When** asked, **Then** the agent politely declines and explains its scope.
5. **Given** a previous chat session, **When** I open it, **Then** the full message history loads and new messages continue the conversation with context.
6. **Given** a follow-up question referencing previous messages (e.g., "What about their international revenue?"), **When** asked, **Then** the agent correctly interprets context from conversation history.
7. **Given** no relevant chunks are found, **When** a question is asked, **Then** the agent informs me and suggests rephrasing.

---

### User Story 4 - Score Companies with Custom Analysis Profiles (Priority: P2)

As an analyst, I want to create an analysis profile with custom financial criteria and run it against a company to see a scored report card with pass/fail per criterion, trends, and an AI narrative summary.

**Why this priority**: Automated quantitative scoring is the second major feature. Depends on financial data from Story 2.

**Independent Test**: Create a "Value Investor" profile with 10 criteria → run against AAPL → see scored results with pass/fail, trend arrows, and AI summary.

**Acceptance Scenarios**:

1. **Given** the system, **When** I create an analysis profile with criteria (each having formula, comparison, threshold, weight, lookback), **Then** it is saved and available for analysis runs.
2. **Given** a company with financial data and a profile, **When** I run analysis, **Then** each criterion shows computed values by year, latest value, threshold, pass/fail, trend (improving/declining/stable), and weighted score.
3. **Given** analysis results, **When** I view them, **Then** the overall weighted score, percentage, and grade (A–F) are displayed with color coding (green/red/yellow).
4. **Given** a criterion that cannot be computed (missing data), **When** evaluated, **Then** it is marked "no_data" and excluded from the max score.
5. **Given** analysis results, **When** AI summary is requested, **Then** a narrative highlights strengths, flags concerns, and notes data gaps.
6. **Given** a custom formula expression like `"income_statement.revenue / balance_sheet.total_assets"`, **When** used in a criterion, **Then** it evaluates correctly using the expression parser.
7. **Given** an invalid custom formula, **When** I save the profile, **Then** I receive a clear validation error.

---

### User Story 5 - Compare Companies Side by Side (Priority: P3)

As an analyst, I want to compare 2–10 companies against the same analysis profile to see a ranked comparison table.

**Why this priority**: Comparison is high value but depends on Stories 2 and 4 being complete for multiple companies.

**Independent Test**: Select AAPL, MSFT, GOOGL + "Value Investor" profile → see ranked comparison table.

**Acceptance Scenarios**:

1. **Given** multiple companies with financial data, **When** I run a comparison against one profile, **Then** a table shows each criterion value for each company, with companies ranked by overall score.
2. **Given** comparison results, **When** I view them, **Then** cells are color-coded pass/fail per company per criterion.
3. **Given** companies with different data periods (e.g., AAPL has 10 years, a newly-added company has 2 years), **When** compared, **Then** each company is scored only on its available data and missing periods are noted.
4. **Given** a company in the comparison set with no financial data at all, **When** the comparison runs, **Then** that company is included with a "no_data" status and ranked last.
5. **Given** comparison results, **When** I want to export, **Then** I can export the comparison table as JSON via the analysis results export endpoint.

---

### User Story 6 - View & Export Financial Data (Priority: P3)

As an analyst, I want to view structured financial data for a company in a table (metrics × years) and export it to CSV for external analysis.

**Why this priority**: Financial data viewing is useful but secondary to chat and scoring.

**Independent Test**: View AAPL financials → see revenue, net income, etc. across years → export CSV.

**Acceptance Scenarios**:

1. **Given** a company with extracted financial data, **When** I view financials, **Then** I see a pivoted table (metrics as rows, fiscal years as columns) covering income statement, balance sheet, and cash flow.
2. **Given** financial data, **When** I export as CSV, **Then** I receive a well-formatted file with all metrics and periods.

---

### User Story 7 - Full Web UI (Priority: P3)

As an analyst, I want a modern, responsive web interface with sidebar navigation, company management, document tracking, chat, analysis dashboards, and settings.

**Why this priority**: The full UI is the delivery vehicle. Can be built last as all features are API-driven.

**Independent Test**: Navigate between dashboard, company detail (all tabs), analysis profiles, comparison, settings — all pages render correctly.

**Acceptance Scenarios**:

1. **Given** the web app, **When** I navigate, **Then** a persistent sidebar shows Dashboard, Companies (with nested list), Analysis Profiles, and Settings.
2. **Given** a company detail page, **When** I view it, **Then** tabs for Overview, Documents, Financials, Chat, and Analysis are available.
3. **Given** the chat tab, **When** I send a message, **Then** tokens stream in real-time, sources are shown after completion, and I can browse past sessions.
4. **Given** any loading operation, **When** in progress, **Then** appropriate loading indicators are shown.
5. **Given** any error, **When** it occurs, **Then** a human-readable message with suggested action is displayed.
6. **Given** the Settings page, **When** I view it, **Then** I see read-only display of current LLM, embedding, and ingestion configuration. (Note: V1 Settings is UI-only — no backend settings API. The frontend reads `NEXT_PUBLIC_*` build-time environment variables. Configuration is managed via environment variables per plan.md Configuration Management.)

---

### Edge Cases

- What happens when SEC EDGAR is temporarily unavailable? → Auto-fetch fails gracefully, already-uploaded documents still process.
- What happens when Azure OpenAI is unavailable? → Chat returns "AI service temporarily unavailable". CRUD and analysis (without AI summary) still work.
- What happens when Qdrant is unavailable? → Chat is unavailable. CRUD and financial analysis still work.
- What happens when a filing has no XBRL data? → Financial extraction logs a warning, stores whatever is available, does not block text ingestion.
- What happens with very large filings (300+ pages)? → System processes them within the 5-minute target; chunking handles any document size.
- What happens when a custom formula divides by zero? → Returns null, criterion marked "no_data", not a crash.
- What happens when the $50/month dev budget is at risk? → Azure Budget alerts fire at 80% ($40) and 100% ($50). V1: Manual operator action per budget-breach runbook — scale-to-zero on all containers, switch to gpt-4o-mini, no managed Redis. V2: Automated budget monitoring and model downgrade.

---

## Requirements *(mandatory)*

### Functional Requirements

**Company Management**
- **FR-100**: System MUST allow creating a company record with a ticker symbol
- **FR-101**: System MUST auto-resolve company name, CIK, sector, and industry from SEC EDGAR
- **FR-102**: System MUST enforce unique ticker constraint
- **FR-103**: System MUST allow listing all companies with summary statistics (doc count, latest filing, readiness)
- **FR-104**: System SHOULD allow updating company metadata
- **FR-105**: System SHOULD allow deleting a company and ALL associated data with confirmation
- **FR-106**: System SHOULD support searching/filtering companies by ticker, name, or sector

**Document Management**
- **FR-200**: System MUST accept file uploads in PDF and HTML formats (max 50 MB)
- **FR-201**: System MUST accept filing metadata: doc_type (10-K, 10-Q, 8-K, 20-F, DEF14A, OTHER), fiscal_year, fiscal_quarter, filing_date, period_end_date
- **FR-202**: System MUST store uploaded files organized by company/type/year
- **FR-203**: System MUST prevent duplicate uploads (same company + doc_type + year + quarter)
- **FR-204**: System MUST track document processing status: uploaded → parsing → parsed → embedding → ready → error
- **FR-205**: System MUST support automatic fetching of filings from SEC EDGAR given a CIK and year range (default: 10-K and 10-Q filings, last 10 years; see API contract for configurable parameters). Returns a task_id for progress polling via `GET /api/v1/tasks/{task_id}`.
- **FR-206**: System MUST respect SEC EDGAR rate limits (max 10 requests/second)
- **FR-207**: System MUST extract text from PDF files preserving paragraph structure
- **FR-208**: System MUST extract text from HTML filings preserving content structure
- **FR-209**: System MUST split extracted text into SEC filing sections using pattern matching
- **FR-210**: System SHOULD support resuming document re-processing from the failed stage (not from scratch)
- **FR-211**: System SHOULD support deletion of individual documents with cascade cleanup

**Ingestion Pipeline**
- **FR-300**: System MUST chunk document sections into segments of 768 tokens (configurable within 512–1024) with 128-token overlap (tiktoken cl100k_base tokenizer)
- **FR-301**: System MUST generate vector embeddings for each chunk
- **FR-302**: System MUST store embeddings in a vector database in a company-scoped collection
- **FR-303**: System MUST attach metadata to each vector (company_id, document_id, doc_type, fiscal_year, section_key, etc.)
- **FR-304**: System MUST extract structured financial data from filings using SEC XBRL API
- **FR-305**: System MUST map XBRL US-GAAP taxonomy tags to internal financial data schema
- **FR-306**: System MUST store structured financial data as JSON, keyed by company + period
- **FR-307**: System MUST process ingestion asynchronously (not blocking API requests)
- **FR-310**: System MUST handle malformed/corrupt files gracefully with clear error messages

**Chat Agent**
- **FR-400**: System MUST provide a conversational AI agent scoped to a single company per session
- **FR-401**: System MUST retrieve top-K relevant chunks via semantic similarity search (configurable top-K, default 15, max 50; configurable score threshold, default 0.65)
- **FR-402**: System MUST inject retrieved chunks as context into the LLM prompt (max 12,000 tokens context budget; max 4,096 tokens response budget)
- **FR-403**: System MUST stream LLM responses token-by-token via Server-Sent Events
- **FR-404**: System MUST include source citations in responses (document type, year, section)
- **FR-405**: System MUST maintain conversation history within a session (configurable limit, default 10 exchanges, 4000 token history budget — whichever limit is reached first; see plan.md RAG Chat Agent Detail for additional context and response token budgets)
- **FR-406**: System MUST persist chat sessions and messages for later retrieval
- **FR-407**: System MUST instruct the LLM to refuse speculation beyond the filing data
- **FR-408**: System MUST return retrieved source chunks with metadata alongside the response
- **FR-409**: System MUST support LLM-based query expansion (generate 2–3 alternative queries, union results with original, deduplicate by chunk_id, re-rank by max score) to improve retrieval recall, controllable via retrieval config toggle
- **FR-413**: System MUST handle the case where no relevant chunks are found

**Financial Analysis Engine**
- **FR-500**: System MUST provide a library of at least 25 built-in financial formulas
- **FR-501**: System MUST allow creating analysis profiles containing 1–30 criteria
- **FR-502**: System MUST support comparison operators: >, >=, <, <=, =, between, trend_up, trend_down
- **FR-503**: System MUST validate custom formula expressions at save time (field references, balanced parentheses, syntax correctness)
- **FR-504**: System MUST handle division-by-zero in formula evaluation gracefully (return null, mark criterion "no_data")
- **FR-505**: System MUST compute each criterion's value across all available years within the lookback window
- **FR-506**: System MUST determine pass/fail based on latest value vs. threshold
- **FR-507**: System MUST compute trend direction (improving/declining/stable) using OLS linear regression over available years (minimum 3 non-null data points; normalised slope = OLS slope / mean of non-null values; normalised slope > +3% → improving, < −3% → declining, otherwise → stable)
- **FR-508**: System MUST compute an overall weighted score and percentage
- **FR-509**: System MUST persist analysis results for historical comparison
- **FR-510**: System MUST assign letter grades based on percentage score: A (90–100%), B (75–89%), C (60–74%), D (40–59%), F (0–39%)
- **FR-511**: System MUST exclude criteria with no computable data ("no_data") from the maximum possible score
- **FR-512**: System SHOULD support custom formula expressions with field references into financial data (see plan.md Expression Parser Specification for DSL syntax: operators, functions, `prev()` references, and field reference patterns)
- **FR-513**: System MUST provide a list of all available built-in formulas via API
- **FR-514**: System SHOULD support comparing multiple companies against the same profile
- **FR-515**: System SHOULD generate an AI narrative summary of analysis results
- **FR-516**: System MUST support criteria categories: profitability, valuation (V1: custom formulas only — market price data is out of scope), growth, liquidity, solvency, efficiency, dividend, quality, custom
- **FR-517**: System MUST support year-over-year growth formulas that reference previous period data

**Data Export**
- **FR-600**: System SHOULD support exporting financial data to CSV format
- **FR-601**: System MUST support exporting analysis results to JSON format

### Non-Functional Requirements

**Performance**
- **NFR-100**: API response time for non-streaming endpoints MUST be under 500ms at p95
- **NFR-101**: Time-to-first-token for chat streaming responses MUST be under 2 seconds
- **NFR-102**: A single 200-page 10-K MUST be fully ingested in under 5 minutes
- **NFR-103**: Vector similarity search (top-15) MUST complete in under 200ms
- **NFR-104**: Analysis of 30 criteria across 10 years of data MUST complete in under 3 seconds

**Scalability**
- **NFR-200**: System MUST support at least 100 companies with 50 documents each (5,000 total documents, 500K+ vectors)

**Data Integrity**
- **NFR-201**: All analysis criteria pass/fail determinations MUST be deterministic and reproducible for the same input data
- **NFR-202**: Ingestion pipeline MUST be idempotent — re-running produces the same result
- **NFR-203**: Multi-step mutations MUST use database transactions to ensure atomicity (company delete cascade, document delete cascade, analysis result persistence)

**Security**
- **NFR-300**: All endpoints except `/health` MUST require API key authentication
- **NFR-301**: User input MUST never appear in LLM system prompts
- **NFR-302**: File uploads MUST be validated via magic bytes (not just extension) and capped at 50 MB

**Reliability**
- **NFR-400**: External service failures (Azure OpenAI, SEC EDGAR, Qdrant) MUST NOT crash the application — circuit breakers and fallbacks MUST be implemented
- **NFR-401**: When Azure OpenAI is unavailable, CRUD operations and analysis (without AI summary) MUST still function
- **NFR-402**: When Qdrant is unavailable, CRUD operations and financial analysis MUST still function; chat returns a clear "unavailable" message

**Observability**
- **NFR-500**: All operations MUST carry a `request_id` for distributed tracing
- **NFR-501**: Structured logging (JSON) MUST be exported via OpenTelemetry to Azure Monitor / Application Insights
- **NFR-502**: Custom metrics MUST be emitted for ingestion throughput, LLM token usage, chat retrieval duration, and analysis duration
- **NFR-503**: No sensitive data (API keys, file contents, full chat messages) MUST appear in logs

**Cost**
- **NFR-600**: Development environment Azure cost MUST stay within the $50/month budget

### Key Entities

- **Company**: Tracked public company (ticker, name, CIK, sector, industry, description). Central entity — all other data belongs to a company.
- **Document**: An SEC filing (10-K, 10-Q) with metadata, processing status, and storage reference. One company has many documents.
- **Section**: A distinct part of a document (e.g., Item 1A — Risk Factors). Sections are split from documents during parsing.
- **Chunk**: A text segment (512–1024 tokens) created by splitting sections. Chunks are embedded and stored in the vector database.
- **Financial Statement**: Structured JSON of income statement, balance sheet, and cash flow data for a company+period. Extracted via XBRL.
- **Chat Session**: A conversation scoped to one company. Contains ordered messages.
- **Chat Message**: A single user or assistant message within a session, with optional source citations.
- **Analysis Profile**: A named collection of financial criteria with thresholds and weights.
- **Analysis Criterion**: A single financial metric within a profile (formula, comparison, threshold, weight, lookback).
- **Analysis Result**: The output of running a profile against a company — overall score, per-criterion details, AI summary.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An analyst can go from "new company registration" to "asking questions about its filings" within 15 minutes (for a company with 5 annual filings auto-fetched from EDGAR).
- **SC-002**: Chat responses include at least one source citation (filing type, year, section) in at least 90% of answers where the retrieval step returns chunks above the score threshold (≥ 0.65 cosine similarity).
- **SC-003**: The chat agent refuses out-of-scope requests (predictions, buy/sell) 100% of the time.
- **SC-004**: A single 200-page 10-K is fully ingested (parsed, chunked, embedded, XBRL extracted) in under 5 minutes.
- **SC-005**: API response time for non-streaming endpoints is under 500ms at p95.
- **SC-006**: Time-to-first-token for chat streaming responses is under 2 seconds.
- **SC-007**: Analysis of 30 criteria across 10 years of data completes in under 3 seconds.
- **SC-008**: The system supports at least 100 companies with 50 documents each (5,000 total documents, 500K+ vectors).
- **SC-009**: All analysis criteria pass/fail determinations are deterministic and reproducible for the same input data.
- **SC-010**: Development environment Azure cost stays within the $50/month budget.
- **SC-011**: Custom formula expressions evaluate correctly for valid input and return clear errors for invalid input.
- **SC-012**: Ingestion pipeline is idempotent — re-running produces the same result.
