# Requirements Checklist: InvestorInsights Platform

**Purpose**: Track implementation status of all functional, non-functional, and success criteria requirements
**Created**: 2025-01-XX
**Feature**: [spec.md](../spec.md)

---

## Functional Requirements

### Company Management

- [ ] **FR-100** System MUST allow creating a company record with a ticker symbol
- [ ] **FR-101** System MUST auto-resolve company name, CIK, sector, and industry from SEC EDGAR
- [ ] **FR-102** System MUST enforce unique ticker constraint
- [ ] **FR-103** System MUST allow listing all companies with summary statistics
- [ ] **FR-104** System SHOULD allow updating company metadata
- [ ] **FR-105** System SHOULD allow deleting a company and ALL associated data
- [ ] **FR-106** System SHOULD support searching/filtering companies

### Document Management

- [ ] **FR-200** System MUST accept file uploads in PDF and HTML formats (max 50 MB)
- [ ] **FR-201** System MUST accept filing metadata (doc_type, fiscal_year, quarter, dates)
- [ ] **FR-202** System MUST store files organized by company/type/year
- [ ] **FR-203** System MUST prevent duplicate uploads
- [ ] **FR-204** System MUST track processing status (uploaded → ready → error)
- [ ] **FR-205** System MUST support auto-fetching from SEC EDGAR
- [ ] **FR-206** System MUST respect SEC EDGAR rate limits (10 req/s)
- [ ] **FR-207** System MUST extract text from PDF preserving structure
- [ ] **FR-208** System MUST extract text from HTML preserving structure
- [ ] **FR-209** System MUST split text into SEC filing sections
- [ ] **FR-210** System SHOULD support re-processing failed documents
- [ ] **FR-211** System SHOULD support individual document deletion with cascade

### Ingestion Pipeline

- [ ] **FR-300** System MUST chunk sections into ~768 token segments (configurable within 512–1024) with overlap
- [ ] **FR-301** System MUST generate vector embeddings for each chunk
- [ ] **FR-302** System MUST store embeddings in company-scoped vector collections
- [ ] **FR-303** System MUST attach metadata to each vector
- [ ] **FR-304** System MUST extract financial data via SEC XBRL API
- [ ] **FR-305** System MUST map XBRL tags to internal schema
- [ ] **FR-306** System MUST store financial data as JSON by company + period
- [ ] **FR-307** System MUST process ingestion asynchronously
- [ ] **FR-310** System MUST handle malformed files gracefully

### Chat Agent

- [ ] **FR-400** System MUST provide company-scoped conversational AI agent
- [ ] **FR-401** System MUST retrieve top-K chunks via semantic search (configurable top-K, default 15, max 50; configurable score threshold, default 0.65)
- [ ] **FR-402** System MUST inject chunks as LLM context
- [ ] **FR-403** System MUST stream responses via SSE
- [ ] **FR-404** System MUST include source citations
- [ ] **FR-405** System MUST maintain conversation history (configurable limit, default 10 exchanges, 4000 token budget)
- [ ] **FR-406** System MUST persist chat sessions and messages
- [ ] **FR-407** System MUST refuse speculation beyond filing data
- [ ] **FR-408** System MUST return source chunks with metadata
- [ ] **FR-409** System MUST support LLM-based query expansion (2–3 alternative queries), controllable via config toggle
- [ ] **FR-413** System MUST handle no-results case

### Financial Analysis Engine

- [ ] **FR-500** System MUST provide 25+ built-in financial formulas
- [ ] **FR-501** System MUST allow creating profiles with 1–30 criteria
- [ ] **FR-502** System MUST support comparison operators (>, >=, <, <=, =, between, trend_up/down)
- [ ] **FR-503** System MUST validate custom formula expressions at save time
- [ ] **FR-504** System MUST handle division-by-zero gracefully (return null, mark "no_data")
- [ ] **FR-505** System MUST compute values across all years in lookback window
- [ ] **FR-506** System MUST determine pass/fail on latest value vs. threshold
- [ ] **FR-507** System MUST compute trend direction via OLS linear regression (±3% normalised slope threshold, min 3 data points)
- [ ] **FR-508** System MUST compute weighted score and percentage
- [ ] **FR-509** System MUST persist analysis results
- [ ] **FR-510** System MUST assign letter grades A–F based on percentage score
- [ ] **FR-511** System MUST exclude "no_data" criteria from maximum possible score
- [ ] **FR-512** System SHOULD support custom formula expressions (see plan.md Expression Parser Spec)
- [ ] **FR-513** System MUST provide built-in formulas list via API
- [ ] **FR-514** System SHOULD support multi-company comparison
- [ ] **FR-515** System SHOULD generate AI narrative summary
- [ ] **FR-516** System MUST support criteria categories (profitability, valuation, growth, liquidity, solvency, efficiency, dividend, quality, custom)
- [ ] **FR-517** System MUST support YoY growth formulas (prev() references)

### Data Export

- [ ] **FR-600** System SHOULD support CSV export of financial data
- [ ] **FR-601** System MUST support JSON export of analysis results

---

## Non-Functional Requirements

### Performance

- [ ] **NFR-100** API response < 500ms p95 (non-streaming)
- [ ] **NFR-101** Chat time-to-first-token < 2 seconds
- [ ] **NFR-102** 200-page 10-K ingestion < 5 minutes
- [ ] **NFR-103** Vector search < 200ms (top-15)
- [ ] **NFR-104** Analysis (30 criteria, 10 years) < 3 seconds

### Scalability

- [ ] **NFR-200** Support at least 100 companies with 50 documents each (5,000 total documents, 500K+ vectors)

### Data Integrity

- [ ] **NFR-201** All analysis criteria pass/fail determinations MUST be deterministic and reproducible
- [ ] **NFR-202** Ingestion pipeline MUST be idempotent — re-running produces the same result
- [ ] **NFR-203** Multi-step mutations MUST use database transactions to ensure atomicity

### Security

- [ ] **NFR-300** All endpoints except `/health` MUST require API key authentication
- [ ] **NFR-301** User input MUST never appear in LLM system prompts
- [ ] **NFR-302** File uploads MUST be validated via magic bytes (not just extension) and capped at 50 MB

### Reliability

- [ ] **NFR-400** External service failures (Azure OpenAI, SEC EDGAR, Qdrant) MUST NOT crash the application — circuit breakers and fallbacks MUST be implemented
- [ ] **NFR-401** When Azure OpenAI is unavailable, CRUD operations and analysis (without AI summary) MUST still function
- [ ] **NFR-402** When Qdrant is unavailable, CRUD operations and financial analysis MUST still function; chat returns a clear "unavailable" message

### Observability

- [ ] **NFR-500** All operations MUST carry a `request_id` for distributed tracing
- [ ] **NFR-501** Structured logging (JSON) MUST be exported via OpenTelemetry to Azure Monitor / Application Insights
- [ ] **NFR-502** Custom metrics MUST be emitted for ingestion throughput, LLM token usage, chat retrieval duration, and analysis duration
- [ ] **NFR-503** No sensitive data (API keys, file contents, full chat messages) MUST appear in logs

### Cost

- [ ] **NFR-600** Development environment Azure cost MUST stay within the $50/month budget

---

## Success Criteria

- [ ] **SC-001** Registration → chat-ready in < 15 min (5 auto-fetched filings)
- [ ] **SC-002** 90%+ answers cite specific filings/sections
- [ ] **SC-003** 100% refusal rate for out-of-scope requests
- [ ] **SC-004** 200-page 10-K ingested in < 5 min
- [ ] **SC-005** API p95 < 500ms
- [ ] **SC-006** Chat TTFT < 2 seconds
- [ ] **SC-007** 30-criteria analysis < 3 seconds
- [ ] **SC-008** 100 companies / 5,000 documents / 500K+ vectors supported
- [ ] **SC-009** Analysis results deterministic and reproducible
- [ ] **SC-010** Dev environment ≤ $50/month Azure spend
- [ ] **SC-011** Custom formulas evaluate correctly or return clear errors
- [ ] **SC-012** Ingestion pipeline is idempotent

---

## Testing Coverage

- [ ] Unit tests: 70% of test suite (all formulas, parser, chunker, splitter, scorer, trend, XBRL mapper)
- [ ] Integration tests: 25% (all API endpoints, full pipeline, chat flow, analysis flow)
- [ ] E2E tests: 5% (company journey, upload+chat journey, analysis journey)
- [ ] Coverage target: 85% line coverage minimum
- [ ] All tests pass in CI (GitHub Actions)
