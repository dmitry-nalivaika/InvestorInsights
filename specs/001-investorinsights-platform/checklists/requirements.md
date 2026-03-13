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

- [ ] **FR-300** System MUST chunk sections into 512–1024 token segments with overlap
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
- [ ] **FR-401** System MUST retrieve top-K chunks via semantic search (configurable top-K, default 15, max 50)
- [ ] **FR-402** System MUST inject chunks as LLM context
- [ ] **FR-403** System MUST stream responses via SSE
- [ ] **FR-404** System MUST include source citations
- [ ] **FR-405** System MUST maintain conversation history (configurable limit, default 10 exchanges, 4000 token budget)
- [ ] **FR-406** System MUST persist chat sessions and messages
- [ ] **FR-407** System MUST refuse speculation beyond filing data
- [ ] **FR-408** System MUST return source chunks with metadata
- [ ] **FR-409** System SHOULD support LLM-based query expansion (2–3 alternative queries) to improve retrieval recall
- [ ] **FR-413** System MUST handle no-results case

### Financial Analysis Engine

- [ ] **FR-500** System MUST provide 25+ built-in financial formulas
- [ ] **FR-501** System MUST allow creating profiles with 1–30 criteria
- [ ] **FR-502** System MUST support comparison operators (>, >=, <, <=, =, between, trend_up/down)
- [ ] **FR-505** System MUST compute values across all years in lookback window
- [ ] **FR-506** System MUST determine pass/fail on latest value vs. threshold
- [ ] **FR-507** System MUST compute trend direction via linear regression
- [ ] **FR-508** System MUST compute weighted score and percentage
- [ ] **FR-509** System MUST persist analysis results
- [ ] **FR-512** System SHOULD support custom formula expressions
- [ ] **FR-514** System SHOULD support multi-company comparison
- [ ] **FR-515** System SHOULD generate AI narrative summary
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
- [ ] **NFR-106** Support 100 companies, 50 docs each (5,000 total)
- [ ] **NFR-107** Support 500K+ vectors per company

### Reliability

- [ ] **NFR-200** Ingestion pipeline is idempotent
- [ ] **NFR-201** Failed steps retryable without data corruption
- [ ] **NFR-202** Uploaded files preserved even if ingestion fails
- [ ] **NFR-203** Multi-step mutations use database transactions
- [ ] **NFR-204** Graceful degradation if LLM unavailable
- [ ] **NFR-205** Graceful degradation if vector store unavailable

### Security

- [ ] **NFR-600** API requires authentication (API key)
- [ ] **NFR-601** File uploads validated (type, size, magic bytes)
- [ ] **NFR-602** All inputs sanitised (parameterised queries)
- [ ] **NFR-603** LLM prompts constructed server-side only
- [ ] **NFR-604** No secrets in logs or responses
- [ ] **NFR-605** Configurable file upload size limit (default 50 MB)
- [ ] **NFR-606** Rate limiting (100/min CRUD, 20/min chat)

### Usability

- [ ] **NFR-400** Responsive web UI (desktop-first, tablet-functional)
- [ ] **NFR-401** Streaming chat character-by-character
- [ ] **NFR-402** Progress indicators for all loading states
- [ ] **NFR-403** Human-readable error messages with suggested actions
- [ ] **NFR-404** Financial figures formatted with precision (`$394.3B`, `48.2%`)

### Maintainability

- [ ] **NFR-500** Consistent code formatting (Ruff/Black, Prettier)
- [ ] **NFR-501** Public functions have docstrings/JSDoc
- [ ] **NFR-502** Schema changes via versioned migrations (Alembic)
- [ ] **NFR-503** Environment-variable driven configuration (12-factor)
- [ ] **NFR-504** All dependencies injected for testability

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
