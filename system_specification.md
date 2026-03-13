document_type: system_specification
version: 2.0.0
status: draft
created: 2025-01-XX
target_audience: LLM-as-implementor (Claude Opus), human reviewers
purpose: >
  Complete specification for an AI-powered public company analysis platform.
  This document should contain ALL information necessary for an implementor
  to build the system end-to-end without further clarification.

Table of Contents

Executive Summary
Glossary & Definitions
User Personas & Stories
Functional Requirements
Non-Functional Requirements
System Architecture
Data Model
API Specification
Ingestion Pipeline
RAG Chat Agent
Financial Analysis Engine
Frontend Specification
Technology Stack
Infrastructure & Deployment
Security
Testing Strategy
Observability & Monitoring
Error Handling & Resilience
Configuration Management
Implementation Phases & Milestones
Appendices


1. Executive Summary

1.1 Problem Statement
Individual investors and small fund analysts who evaluate public companies face two core challenges:

Information Overload: SEC filings (10-K, 10-Q) are dense, 100-300 page documents. A 10-year analysis of a single company requires reading 50+ filings comprising thousands of pages. Extracting insights about business direction, risk changes, and strategic shifts requires significant time.

Inconsistent Quantitative Analysis: Evaluating financial health requires computing dozens of metrics (margins, returns, leverage ratios, growth rates) across multiple years, comparing them against personal investment thresholds, and identifying trends. Doing this manually in spreadsheets is error-prone and time-consuming, especially when comparing multiple companies.

1.2 Solution
A self-hosted platform that:

Stores and indexes SEC filings per company, organized by type and period
Provides an AI conversational agent (per company) that has "read" all uploaded filings and can answer qualitative questions about the business, risks, strategy, competitive position, and changes over time — always grounding answers in specific filings
Automates quantitative analysis by extracting structured financial data from filings, computing user-defined financial metrics/ratios, comparing them against user-defined thresholds, and producing a scored report card

1.3 Key Design Principles

| Principle | Description |
| :-- | :-- |
| Company-scoped | All data, chat, and analysis is organized per-company. The company is the central entity. |
| User-defined criteria | The financial scoring system is fully configurable. Users define what to measure, how to compute it, what thresholds to apply, and how to weight each criterion. |
| Grounded AI | The chat agent must ONLY answer based on uploaded filings. It must cite sources. It must refuse to speculate beyond the data. |
| Self-hosted | The platform runs on user's own infrastructure (local Docker or cloud VPS). Only outbound calls are to LLM APIs and SEC EDGAR. |
| Single user | V1 is designed for a single analyst. Authentication is simple (API key or basic auth). Multi-user is a future consideration. |
| Offline-capable data | Once filings are ingested, all analysis and chat works without re-fetching from SEC. Only LLM inference requires external API calls. |

2. Glossary & Definitions

| Term | Definition |
| :-- | :-- |
| 10-K | Annual report filed by public companies with the SEC. Contains business overview, risk factors, financial statements, MD&A, and more. Organized into Items 1-15. |
| 10-Q | Quarterly report (filed for Q1, Q2, Q3; Q4 is covered by 10-K). Smaller scope than 10-K, focuses on interim financial statements and updates. |
| 8-K | Current report for material events (acquisitions, leadership changes, etc.). Optional support in V1. |
| CIK | Central Index Key — SEC's unique identifier for each filing entity. Example: Apple Inc = 0000320193. |
| Accession Number | SEC's unique identifier for each individual filing. Format: 0000320193-24-000123. |
| EDGAR | Electronic Data Gathering, Analysis, and Retrieval — SEC's filing system and public API. |
| XBRL | eXtensible Business Reporting Language — structured data format embedded in SEC filings. Enables machine-readable extraction of financial line items. |
| RAG | Retrieval-Augmented Generation — pattern where relevant documents are retrieved and injected into LLM context to ground responses in factual data. |
| Chunk | A segment of text (typically 512-1024 tokens) created by splitting a larger document. Chunks are embedded and stored in the vector database for semantic search. |
| Embedding | A dense vector representation of text (typically 1536-3072 dimensions) that captures semantic meaning. Similar texts have similar embeddings. |
| Vector Store | A database optimized for storing and searching high-dimensional vectors by similarity (cosine distance, dot product). |
| Analysis Profile | A user-defined collection of financial criteria with thresholds, used to score/evaluate a company. |
| Criterion (pl. Criteria) | A single financial metric within an analysis profile. Consists of a formula, comparison operator, threshold value(s), and weight. |
| Formula | A named computation that takes structured financial data as input and produces a numeric value. Example: roe = Net Income / Total Equity. |
| Filing Period | The time period covered by a filing. Identified by fiscal year and fiscal quarter (null for annual). |
| Section | A distinct part of an SEC filing (e.g., Item 1 — Business, Item 1A — Risk Factors, Item 7 — MD&A). |

3. User Personas & Stories

3.1 Primary Persona: Independent Equity Analyst
Name: Alex Background: Self-directed investor who manages their own portfolio. Has 5-15 years of investing experience. Follows a value investing or quality-growth investment philosophy. Currently analyzes 20-50 companies per year by reading SEC filings and building spreadsheet models.

Pain Points:

Spends 4-8 hours per company reading annual reports
Maintaining spreadsheets for financial metrics across companies is tedious
Difficulty remembering specific details from filings read months ago
No systematic way to compare companies against a consistent set of criteria
Missing important changes in risk factors or business strategy between years
3.2 User Stories
3.2.1 Company Management

US-010: As an analyst, I want to register a new company by ticker symbol
        so that I can begin uploading and analyzing its filings.
        Acceptance Criteria:
        - I provide a ticker (e.g., "AAPL") and the system creates a company record
        - The system auto-populates company name, CIK, sector, and industry from SEC EDGAR
        - If the ticker is already registered, I receive an appropriate error
        - The company appears in my company list immediately

US-011: As an analyst, I want to see a list of all my tracked companies
        with a summary of how many filings are loaded and analysis status.
        Acceptance Criteria:
        - Each company shows: ticker, name, sector, document count, latest filing date
        - Companies are sortable by name, ticker, or latest filing date
        - I can search/filter the company list

US-012: As an analyst, I want to view a company detail page that shows
        all uploaded filings, financial data availability, and recent chat sessions.
        Acceptance Criteria:
        - Timeline view of all filings with their ingestion status
        - Summary of available financial data periods
        - Links to start a new chat or open recent sessions
        - Link to run analysis

3.2.2 Document Upload & Ingestion

US-020: As an analyst, I want to upload an SEC filing (PDF or HTML) for a
        specific company and filing period so that the AI can learn from it.
        Acceptance Criteria:
        - I can select the company, filing type (10-K/10-Q), fiscal year, and quarter
        - I upload a single file (PDF or HTML)
        - The file is stored and queued for processing
        - I see immediate feedback that the upload was received
        - I can track the processing status (uploaded → parsing → embedding → ready)

US-021: As an analyst, I want the system to automatically fetch filings from
        SEC EDGAR for a company so I don't have to manually download them.
        Acceptance Criteria:
        - I specify the company and how many years back to fetch (default: 10)
        - The system queries SEC EDGAR for all 10-K and 10-Q filings for that period
        - Each filing is downloaded, stored, and queued for ingestion
        - I can see progress of the bulk fetch operation
        - Filings that already exist in the system are skipped (no duplicates)
        - The system respects SEC EDGAR rate limits (10 requests/second max)

US-022: As an analyst, I want to see the ingestion status of all documents
        for a company so I know when the system is ready for chat/analysis.
        Acceptance Criteria:
        - Status displayed per document: uploaded, parsing, parsed, embedding, ready, error
        - For errors, I see the error message and can retry the ingestion
        - Overall company readiness indicator (e.g., "42 of 45 documents ready")

US-023: As an analyst, I want to re-ingest a document that failed processing
        so I can fix transient errors.
        Acceptance Criteria:
        - Documents in "error" status show a "Retry" action
        - Retrying resets the status and re-runs the full pipeline
        - The original file is preserved (not re-uploaded)

US-024: As an analyst, I want to delete a document and all its derived data
        (chunks, embeddings, financial data) if it was uploaded in error.
        Acceptance Criteria:
        - Deleting removes: the file from storage, all chunks from vector DB,
          all section records, associated financial data if it was the sole source
        - Requires confirmation before deletion

3.2.3 AI Chat Agent

US-030: As an analyst, I want to start a new chat session scoped to a specific
        company so I can ask questions about that company's filings.
        Acceptance Criteria:
        - Chat is always scoped to exactly one company
        - The agent introduces itself and states which filings it has access to
        - The agent knows the company name, ticker, and available filing date range

US-031: As an analyst, I want to ask the agent qualitative questions about
        the company and receive answers grounded in the actual SEC filings.
        Example questions:
        - "What are the main risk factors for this company?"
        - "How has the business model changed over the last 5 years?"
        - "What did management say about competition in the 2023 10-K?"
        - "Compare the revenue segments between 2020 and 2024"
        - "What are the key items in their litigation disclosures?"
        Acceptance Criteria:
        - Answers reference specific filings (e.g., "According to the FY2023 10-K, Item 1A...")
        - The agent uses information from multiple filings when appropriate
        - The agent clearly states when information is not available in the filings
        - Responses stream in real-time (token by token)

US-032: As an analyst, I want the agent to refuse to answer questions that
        cannot be grounded in the uploaded filings.
        Acceptance Criteria:
        - If asked about future predictions, stock price, or buy/sell recommendations,
          the agent politely declines and explains its scope
        - If the question requires data not in the filings, the agent says so
        - The agent never fabricates financial numbers

US-033: As an analyst, I want to see which filing sections were used to
        generate each response so I can verify the information.
        Acceptance Criteria:
        - Each response includes a "Sources" section listing the retrieved chunks
        - Sources show: document type, fiscal year/quarter, section title, relevance score
        - I can click a source to see the full chunk text

US-034: As an analyst, I want to continue a previous chat session so I can
        build on earlier conversations.
        Acceptance Criteria:
        - I can see a list of past sessions with title and last message date
        - Opening a session loads the full message history
        - New messages are added to the same session with full context

US-035: As an analyst, I want the agent to handle follow-up questions that
        reference previous messages in the conversation.
        Acceptance Criteria:
        - "What about their international revenue?" after discussing revenue segments
          correctly interprets "their" as the company being discussed
        - Conversation context window includes last 10 exchanges (configurable)

3.2.4 Financial Analysis

US-040: As an analyst, I want to create an analysis profile with my custom
        criteria so I can score companies consistently.
        Acceptance Criteria:
        - I define a profile name and description
        - I add 1-30 criteria, each with: name, category, formula, comparison,
          threshold(s), weight, and lookback period
        - I can choose from a library of built-in formulas or define custom ones
        - I can mark a profile as my default

US-041: As an analyst, I want to run my analysis profile against a company
        and see a scored report card.
        Acceptance Criteria:
        - Each criterion shows: computed values by year, latest value, threshold,
          pass/fail status, and trend (improving/declining/stable)
        - Overall weighted score is computed and displayed as percentage
        - Results are color-coded: green (pass), red (fail), yellow (borderline)
        - Results are saved and can be viewed later without re-running

US-042: As an analyst, I want to see historical values for each metric
        charted over time so I can visualize trends.
        Acceptance Criteria:
        - Line chart showing metric values across years
        - Threshold displayed as a horizontal reference line
        - Clear labeling of passing vs. failing years

US-043: As an analyst, I want to compare two or more companies side by side
        using the same analysis profile.
        Acceptance Criteria:
        - I select 2-10 companies and one analysis profile
        - A comparison table shows each criterion value for each company
        - Companies are ranked by overall score
        - Color coding shows pass/fail per cell

US-044: As an analyst, I want the system to generate an AI narrative summary
        of the analysis results explaining the key findings.
        Acceptance Criteria:
        - Summary highlights strengths (consistently passing criteria)
        - Summary flags concerns (failing criteria, declining trends)
        - Summary notes any data gaps or insufficient history
        - Summary is stored with the analysis results

US-045: As an analyst, I want to edit my analysis profile (add/remove/modify
        criteria) and re-run analysis to see updated results.
        Acceptance Criteria:
        - Changes to a profile create a new version (old results reference old version)
        - Re-running produces a new result set with the updated criteria

US-046: As an analyst, I want to define custom formulas using a simple
        expression syntax when the built-in formulas don't cover my needs.
        Acceptance Criteria:
        - I can write expressions like:
          "income_statement.operating_income / (balance_sheet.total_assets - balance_sheet.total_current_liabilities)"
        - The expression parser supports: +, -, *, /, parentheses, abs(), min(), max()
        - Field references use dot notation into the financial_statements JSON structure
        - Invalid expressions produce clear error messages at profile save time
        - Custom formulas can reference previous period data with prev() wrapper:
          "(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)"

3.2.5 Data Export

US-050: As an analyst, I want to export analysis results to a PDF report
        so I can share findings or keep offline records.
        Acceptance Criteria:
        - PDF includes: company info, analysis profile summary, scored criteria table,
          trend charts, AI narrative summary
        - Professional formatting with header, date, and company branding

US-051: As an analyst, I want to export raw financial data to CSV/Excel
        so I can do additional analysis in my own tools.
        Acceptance Criteria:
        - Export includes all available financial statement data for selected periods
        - Columns: metric name, and one column per fiscal year/quarter
        - Available for download via API and UI

4. Functional Requirements
4.1 Company Management (FR-1xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-100 | System SHALL allow creating a company record with at minimum a ticker symbol | Must |
| FR-101 | System SHALL auto-resolve company name, CIK, sector, and industry from SEC EDGAR when a ticker is provided | Must |
| FR-102 | System SHALL enforce unique ticker constraint (no duplicate companies) | Must |
| FR-103 | System SHALL allow listing all companies with summary statistics | Must |
| FR-104 | System SHALL allow updating company metadata (name, sector, etc.) | Should |
| FR-105 | System SHALL allow deleting a company and ALL associated data (documents, chunks, financials, chats, results) with confirmation | Should |
| FR-106 | System SHALL support searching/filtering companies by ticker, name, or sector | Should |

4.2 Document Management (FR-2xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-200 | System SHALL accept file uploads in PDF and HTML formats | Must |
| FR-201 | System SHALL accept filing metadata: doc_type (10-K, 10-Q, 8-K), fiscal_year, fiscal_quarter, filing_date, period_end_date | Must |
| FR-202 | System SHALL store uploaded files in object storage (S3/MinIO) organized by company_id/doc_type/year/ | Must |
| FR-203 | System SHALL prevent duplicate uploads (same company + doc_type + fiscal_year + fiscal_quarter) | Must |
| FR-204 | System SHALL track document processing status: uploaded → parsing → parsed → embedding → ready → error | Must |
| FR-205 | System SHALL support automatic fetching of filings from SEC EDGAR given a company CIK and year range | Must |
| FR-206 | System SHALL respect SEC EDGAR rate limits (max 10 requests/second, User-Agent header required) | Must |
| FR-207 | System SHALL extract text from PDF files preserving paragraph structure | Must |
| FR-208 | System SHALL extract text from HTML filings (stripping formatting, preserving content structure) | Must |
| FR-209 | System SHALL split extracted text into SEC filing sections (Items) using pattern matching | Must |
| FR-210 | System SHALL support re-processing a document from any failed stage | Should |
| FR-211 | System SHALL support deletion of individual documents with cascade cleanup | Should |
| FR-212 | System SHALL report file size, page count, and token count per document | Should |
| FR-213 | System SHALL support 8-K filings as an optional document type | Could |
| FR-214 | System SHALL support 20-F filings (foreign private issuers) as an optional document type | Could |

4.3 Ingestion Pipeline (FR-3xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-300 | System SHALL chunk document sections into segments of 512-1024 tokens with 10-20% overlap | Must |
| FR-301 | System SHALL generate vector embeddings for each chunk using a configurable embedding model | Must |
| FR-302 | System SHALL store embeddings in a vector database in a company-scoped namespace/collection | Must |
| FR-303 | System SHALL attach metadata to each vector: company_id, document_id, doc_type, fiscal_year, fiscal_quarter, section_key, section_title, filing_date | Must |
| FR-304 | System SHALL extract structured financial data from filings using SEC XBRL API (companyfacts endpoint) | Must |
| FR-305 | System SHALL map XBRL US-GAAP taxonomy tags to internal financial data schema | Must |
| FR-306 | System SHALL store structured financial data as JSON in PostgreSQL, keyed by company + period | Must |
| FR-307 | System SHALL process ingestion asynchronously (not blocking the API request) | Must |
| FR-308 | System SHALL support processing multiple documents concurrently (configurable worker count) | Should |
| FR-309 | System SHALL emit progress events during ingestion (for status tracking) | Should |
| FR-310 | System SHALL handle malformed/corrupt PDFs gracefully with clear error messages | Must |
| FR-311 | System SHALL deduplicate chunks that are identical within the same document | Should |

4.4 Chat Agent (FR-4xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-400 | System SHALL provide a conversational AI agent scoped to a single company per session | Must |
| FR-401 | System SHALL retrieve top-K relevant document chunks via semantic similarity search for each user message | Must |
| FR-402 | System SHALL inject retrieved chunks as context into the LLM prompt | Must |
| FR-403 | System SHALL stream LLM responses token-by-token via Server-Sent Events (SSE) | Must |
| FR-404 | System SHALL include source citations in responses (document type, year, quarter, section) | Must |
| FR-405 | System SHALL maintain conversation history within a session (up to configurable limit, default 10 exchanges) | Must |
| FR-406 | System SHALL persist chat sessions and messages for later retrieval | Must |
| FR-407 | System SHALL instruct the LLM to refuse speculation beyond the filing data | Must |
| FR-408 | System SHALL return the list of retrieved source chunks with their metadata alongside the response | Must |
| FR-409 | System SHALL support configurable retrieval parameters: top_k (default 15), score_threshold (default 0.65) | Should |
| FR-410 | System SHALL support filtering retrieval by date range, document type, or section | Should |
| FR-411 | System SHALL auto-generate session titles based on the first user message | Should |
| FR-412 | System SHALL support deleting chat sessions | Should |
| FR-413 | System SHALL handle the case where no relevant chunks are found (inform user, suggest rephrasing) | Must |

4.5 Financial Analysis Engine (FR-5xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-500 | System SHALL provide a library of at least 20 built-in financial formulas (see Appendix A) | Must |
| FR-501 | System SHALL allow creating analysis profiles containing 1-30 criteria | Must |
| FR-502 | System SHALL support comparison operators: >, >=, <, <=, =, between, trend_up, trend_down | Must |
| FR-503 | System SHALL support numeric thresholds (single value, or low/high range for "between") | Must |
| FR-504 | System SHALL support weighting criteria for aggregate scoring | Must |
| FR-505 | System SHALL compute each criterion's value across all available years within the lookback window | Must |
| FR-506 | System SHALL determine pass/fail for each criterion based on the latest value vs. threshold | Must |
| FR-507 | System SHALL compute trend direction (improving/declining/stable) using linear regression over available years | Must |
| FR-508 | System SHALL compute an overall weighted score and percentage | Must |
| FR-509 | System SHALL persist analysis results for historical comparison | Must |
| FR-510 | System SHALL support multiple analysis profiles (e.g., "Value Investor", "Growth Screen", "Dividend Focus") | Must |
| FR-511 | System SHALL support marking one profile as the default | Should |
| FR-512 | System SHALL support custom formula expressions with field references into financial data JSON | Should |
| FR-513 | System SHALL validate custom formula expressions at save time and provide clear error messages | Should |
| FR-514 | System SHALL support comparing multiple companies against the same profile | Should |
| FR-515 | System SHALL generate an AI narrative summary of analysis results | Should |
| FR-516 | System SHALL allow using the chat agent to explain analysis results ("Why did ROE fail?") | Could |
| FR-517 | System SHALL support year-over-year growth formulas that reference previous period data | Must |

4.6 Data Export (FR-6xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-600 | System SHALL support exporting financial data to CSV format | Should |
| FR-601 | System SHALL support exporting analysis results to JSON format | Must |
| FR-602 | System SHALL support generating a PDF analysis report | Could |
| FR-603 | System SHALL support exporting chat session transcripts | Could |

5. Non-Functional Requirements
5.1 Performance (NFR-1xx)

| ID | Requirement | Target |
| :-- | :-- | :-- |
| NFR-100 | API response time for non-streaming endpoints | < 500ms p95 |
| NFR-101 | Time-to-first-token for chat streaming responses | < 2 seconds |
| NFR-102 | Document ingestion throughput (single 10-K, ~200 pages) | < 5 minutes end-to-end |
| NFR-103 | Vector similarity search latency | < 200ms for top-15 results |
| NFR-104 | Financial analysis computation for one company (30 criteria, 10 years) | < 3 seconds |
| NFR-105 | Concurrent ingestion capacity | At least 5 documents simultaneously |
| NFR-106 | System SHALL support at least 100 companies with 50 documents each (5,000 total documents) | Must |
| NFR-107 | System SHALL handle at least 500,000 vector embeddings per company collection | Must |

5.2 Reliability (NFR-2xx)

| ID | Requirement | Target |
| :-- | :-- | :-- |
| NFR-200 | Ingestion pipeline SHALL be idempotent (re-running produces same result) | Must |
| NFR-201 | Failed ingestion steps SHALL be retryable without data corruption | Must |
| NFR-202 | System SHALL not lose uploaded files even if ingestion fails | Must |
| NFR-203 | Database operations SHALL use transactions for multi-step mutations | Must |
| NFR-204 | System SHALL gracefully degrade if LLM API is unavailable (chat unavailable, analysis still works) | Should |
| NFR-205 | System SHALL gracefully degrade if vector store is unavailable (chat unavailable, CRUD still works) | Should |

5.3 Scalability (NFR-3xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-300 | System is designed for single-user deployment but should support multiple concurrent browser tabs/sessions | Must |
| NFR-301 | Worker pool size SHALL be configurable (1-10 workers) | Must |
| NFR-302 | Vector store collections SHALL be partitioned per company to allow independent scaling | Must |
| NFR-303 | Financial data storage SHALL use JSONB for flexibility but with indexed query paths | Should |

5.4 Usability (NFR-4xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-400 | Web UI SHALL be responsive (desktop-first, functional on tablet) | Should |
| NFR-401 | Chat interface SHALL display streaming responses character-by-character | Must |
| NFR-402 | All loading states SHALL show progress indicators | Must |
| NFR-403 | Error states SHALL display human-readable messages with suggested actions | Must |
| NFR-404 | Financial figures SHALL be formatted with appropriate precision and units (e.g., "$394.3B", "48.2%") | Must |

5.5 Maintainability (NFR-5xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-500 | Code SHALL follow consistent formatting (Black for Python, Prettier for TypeScript) | Must |
| NFR-501 | All public functions/methods SHALL have docstrings/JSDoc | Must |
| NFR-502 | Database schema changes SHALL use versioned migrations (Alembic) | Must |
| NFR-503 | Configuration SHALL be environment-variable driven (12-factor app) | Must |
| NFR-504 | All service dependencies SHALL be injected (not hard-coded) for testability | Must |

5.6 Security (NFR-6xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-600 | API SHALL require authentication (API key in header for V1) | Must |
| NFR-601 | Uploaded files SHALL be validated (file type, size limits) | Must |
| NFR-602 | All user inputs SHALL be sanitized before database queries | Must |
| NFR-603 | LLM prompts SHALL be constructed server-side (user input is never directly used as system prompt) | Must |
| NFR-604 | API keys and secrets SHALL never appear in logs or responses | Must |
| NFR-605 | File upload size limit SHALL be configurable (default: 50MB per file) | Must |
| NFR-606 | Rate limiting SHALL be applied to API endpoints (default: 100 req/min for CRUD, 20 req/min for chat) | Should |

6. System Architecture

6.1 High-Level Architecture Diagram

┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                                                                              │
│    ┌────────────────────────────────────────────────────────────────────┐     │
│    │                    Next.js Web Application                        │     │
│    │                                                                    │     │
│    │  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌────────────┐   │     │
│    │  │ Company  │  │  Document    │  │   Chat    │  │  Analysis  │   │     │
│    │  │ Manager  │  │  Manager     │  │ Interface │  │ Dashboard  │   │     │
│    │  └──────────┘  └──────────────┘  └───────────┘  └────────────┘   │     │
│    └───────────────────────────┬────────────────────────────────────────┘     │
│                                │  HTTP/SSE                                    │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                           API LAYER (FastAPI)                                  │
│                                                                                │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────────┐      │
│  │  /companies │  │  /documents  │  │  /chat   │  │  /analysis         │      │
│  │  CRUD       │  │  upload,     │  │  SSE     │  │  profiles, run,    │      │
│  │             │  │  status,     │  │  stream  │  │  results, compare  │      │
│  │             │  │  fetch-sec   │  │          │  │                    │      │
│  └──────┬──────┘  └──────┬───────┘  └────┬─────┘  └─────────┬──────────┘      │
│         │                │               │                   │                 │
│  ┌──────┴────────────────┴───────────────┴───────────────────┴──────────────┐  │
│  │                        SERVICE LAYER                                     │  │
│  │                                                                          │  │
│  │  ┌────────────────┐  ┌─────────────────┐  ┌───────────────────────────┐  │  │
│  │  │  CompanyService│  │ DocumentService │  │  ChatService              │  │  │
│  │  │                │  │                 │  │  ┌─────────────────────┐  │  │  │
│  │  │  • create      │  │ • upload        │  │  │  CompanyChatAgent   │  │  │  │
│  │  │  • resolve CIK │  │ • fetch_from_sec│  │  │  • retrieve chunks  │  │  │  │
│  │  │  • list/get    │  │ • get_status    │  │  │  • build prompt     │  │  │  │
│  │  │  • delete      │  │ • retry         │  │  │  • stream response  │  │  │  │
│  │  │                │  │ • delete        │  │  │  • save history     │  │  │  │
│  │  └────────────────┘  └────────┬────────┘  │  └─────────────────────┘  │  │  │
│  │                               │           └───────────────────────────┘  │  │
│  │  ┌────────────────────────────┴──────────────────────────────────────┐   │  │
│  │  │                  IngestionPipeline                                │   │  │
│  │  │                                                                   │   │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │   │  │
│  │  │  │ Document │ │ Section  │ │Financial │ │  Text    │ │Embedding│ │   │  │
│  │  │  │ Parser   │ │ Splitter │ │Extractor │ │ Chunker  │ │Service │ │   │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │   │  │
│  │  └───────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                          │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐   │  │
│  │  │              FinancialAnalysisEngine                              │   │  │
│  │  │                                                                   │   │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │   │  │
│  │  │  │ FormulaEngine│  │ Threshold    │  │ Trend Detection      │   │   │  │
│  │  │  │ (registry +  │  │ Evaluator    │  │ (linear regression)  │   │   │  │
│  │  │  │  custom DSL) │  │              │  │                      │   │   │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │   │  │
│  │  └───────────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└───────────────┬──────────────┬───────────────┬──────────────┬─────────────────┘
                │              │               │              │
                ▼              ▼               ▼              ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                          │
│                                                                                │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL  │  │  Qdrant       │  │  MinIO / S3  │  │  Redis           │  │
│  │              │  │  (Vector DB)  │  │  (Object     │  │  (Task Queue,    │  │
│  │  • companies │  │               │  │   Storage)   │  │   Cache)         │  │
│  │  • documents │  │  • per-company│  │              │  │                  │  │
│  │  • sections  │  │    collections│  │  • raw PDFs/ │  │  • Celery broker │  │
│  │  • chunks    │  │  • 3072-dim   │  │    HTML files│  │  • session cache │  │
│  │  • financials│  │    vectors    │  │  • organized │  │  • rate limiting │  │
│  │  • profiles  │  │  • payload    │  │    by company│  │                  │  │
│  │  • criteria  │  │    metadata   │  │    /type/year│  │                  │  │
│  │  • results   │  │               │  │              │  │                  │  │
│  │  • chats     │  │               │  │              │  │                  │  │
│  └──────────────┘  └───────────────┘  └──────────────┘  └──────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
                │                                    │
                ▼                                    ▼
┌────────────────────────────┐    ┌────────────────────────────────────────────┐
│    EXTERNAL SERVICES       │    │         ASYNC WORKER POOL                  │
│                            │    │                                            │
│  • SEC EDGAR API           │    │  Celery Workers (configurable 1-10)        │
│    (companyfacts, filings) │    │                                            │
│  • OpenAI API              │    │  Queues:                                   │
│    (embeddings, chat)      │    │    • ingestion (document processing)       │
│  • (optional) Cohere API   │    │    • analysis  (report generation)         │
│  • (optional) Anthropic    │    │    • sec_fetch (EDGAR downloading)         │
│                            │    │                                            │
└────────────────────────────┘    └────────────────────────────────────────────┘

6.2 Component Responsibilities

| Component | Responsibility | Statefulness |
| :-- | :-- | :-- |
| FastAPI App | HTTP request handling, validation, routing, SSE streaming, authentication | Stateless |
| CompanyService | Company CRUD, CIK resolution from SEC | Stateless |
| DocumentService | File upload to S3, metadata CRUD, triggering ingestion | Stateless |
| IngestionPipeline | Document parsing, section splitting, chunking, embedding, financial extraction | Stateless (all state in DB) |
| ChatService | Session management, message persistence | Stateless |
| CompanyChatAgent | RAG retrieval, prompt construction, LLM interaction, streaming | Stateless per request (loads context fresh) |
| FinancialAnalysisEngine | Formula computation, threshold evaluation, trend detection, scoring | Stateless |
| Celery Workers | Async task execution for ingestion and analysis | Stateless (pull from queue) |
| PostgreSQL | Relational data: companies, documents, financials, profiles, results, chat history | Persistent |
| Qdrant | Vector storage and similarity search | Persistent |
| MinIO/S3 | Raw file storage | Persistent |
| Redis | Celery broker, caching, rate limiting | Semi-persistent |

6.3 Data Flow Diagrams
6.3.1 Document Upload & Ingestion Flow

User                  API                   Worker              S3      Postgres    Qdrant
  │                    │                      │                  │         │          │
  │── POST /documents ─▶│                     │                  │         │          │
  │   (file + metadata) │                     │                  │         │          │
  │                    │── store file ────────────────────────────▶│        │          │
  │                    │── create doc record ─────────────────────────────▶│          │
  │                    │   (status=uploaded)   │                  │         │          │
  │                    │── enqueue task ──────▶│                  │         │          │
  │◀── 202 Accepted ──│                      │                  │         │          │
  │   (document_id)    │                      │                  │         │          │
  │                    │                      │── fetch file ────▶│        │          │
  │                    │                      │◀── file content ──│        │          │
  │                    │                      │                  │         │          │
  │                    │                      │── update status ──────────▶│          │
  │                    │                      │   (parsing)       │         │          │
  │                    │                      │                  │         │          │
  │                    │                      │── parse PDF/HTML  │         │          │
  │                    │                      │── split sections  │         │          │
  │                    │                      │── save sections ──────────▶│          │
  │                    │                      │                  │         │          │
  │                    │                      │── extract XBRL ──┼── SEC API         │
  │                    │                      │── save financials ────────▶│          │
  │                    │                      │                  │         │          │
  │                    │                      │── update status ──────────▶│          │
  │                    │                      │   (embedding)     │         │          │
  │                    │                      │                  │         │          │
  │                    │                      │── chunk text      │         │          │
  │                    │                      │── generate embeddings (OpenAI API)    │
  │                    │                      │── upsert vectors ─────────────────────▶│
  │                    │                      │── save chunk records ─────▶│          │
  │                    │                      │                  │         │          │
  │                    │                      │── update status ──────────▶│          │
  │                    │                      │   (ready)         │         │          │

  6.3.2 Chat Flow

  User                  API                   ChatAgent          Qdrant    OpenAI     Postgres
  │                    │                      │                  │         │          │
  │── POST /chat ─────▶│                     │                  │         │          │
  │   (message, session)│                     │                  │         │          │
  │                    │── load company info ─────────────────────────────────────────▶│
  │                    │── load chat history ─────────────────────────────────────────▶│
  │                    │── create agent ─────▶│                  │         │          │
  │                    │                      │── embed query ───────────▶│          │
  │                    │                      │◀── query vector ──────────│          │
  │                    │                      │── search ────────▶│        │          │
  │                    │                      │◀── top-K chunks ──│        │          │
  │                    │                      │                  │         │          │
  │                    │                      │── build prompt    │         │          │
  │                    │                      │   (system + history + context + question)
  │                    │                      │── stream chat ───────────▶│          │
  │                    │                      │◀── token stream ──────────│          │
  │◀── SSE stream ─────│◀── tokens ──────────│                  │         │          │
  │   (token by token)  │                      │                  │         │          │
  │                    │                      │── save messages ──────────────────────▶│
  │◀── SSE [DONE] ─────│                     │                  │         │          │

  6.3.3 Analysis Flow

  User                  API              AnalysisEngine         Postgres    OpenAI
  │                    │                      │                  │          │
  │── POST /analysis  ─▶│                     │                  │          │
  │   /run/{co}/{prof}  │                     │                  │          │
  │                    │── load financials ────────────────────────▶│       │
  │                    │── load criteria ──────────────────────────▶│       │
  │                    │── run engine ────────▶│                  │          │
  │                    │                      │── compute formulas│         │
  │                    │                      │   (per year, per  │         │
  │                    │                      │    criterion)     │         │
  │                    │                      │── evaluate thresholds      │
  │                    │                      │── detect trends   │         │
  │                    │                      │── compute scores  │         │
  │                    │◀── AnalysisReport ───│                  │          │
  │                    │                      │                  │          │
  │                    │── generate summary ──────────────────────────────▶│
  │                    │◀── AI narrative ─────────────────────────────────│
  │                    │── save results ──────────────────────────▶│       │
  │◀── 200 OK ────────│                      │                  │          │
  │   (full report)    │                      │                  │          │

7. Data Model
7.1 Entity Relationship Diagram

┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  companies   │     │    documents     │     │ document_sections │
│──────────────│     │──────────────────│     │───────────────────│
│ id (PK)      │◀───┤│ id (PK)         │◀───┤│ id (PK)          │
│ ticker       │  1:N│ company_id (FK)  │  1:N│ document_id (FK) │
│ name         │     │ doc_type         │     │ section_key      │
│ cik          │     │ fiscal_year      │     │ section_title    │
│ sector       │     │ fiscal_quarter   │     │ content_text     │
│ industry     │     │ filing_date      │     │ token_count      │
│ description  │     │ period_end_date  │     └───────┬───────────┘
│ created_at   │     │ sec_accession    │             │
│ updated_at   │     │ source_url       │             │ 1:N
└──────┬───────┘     │ storage_key      │             ▼
       │             │ status           │     ┌───────────────────┐
       │             │ error_message    │     │ document_chunks   │
       │             │ file_size_bytes  │     │───────────────────│
       │             │ page_count       │     │ id (PK)          │
       │             │ created_at       │     │ section_id (FK)  │
       │             │ updated_at       │     │ document_id (FK) │
       │             └──────┬───────────┘     │ company_id (FK)  │
       │                    │                 │ chunk_index      │
       │                    │ 1:N             │ content          │
       │                    ▼                 │ token_count      │
       │           ┌──────────────────┐       │ embedding_model  │
       │           │financial_stmts   │       │ vector_id        │
       │           │──────────────────│       │ metadata (JSONB) │
       │           │ id (PK)         │       │ created_at       │
       ├──────────▶│ company_id (FK) │       └──────────────────┘
       │     1:N   │ document_id(FK) │
       │           │ fiscal_year     │
       │           │ fiscal_quarter  │
       │           │ period_end_date │
       │           │ statement_data  │
       │           │   (JSONB)       │
       │           └─────────────────┘
       │
       │           ┌──────────────────┐       ┌───────────────────┐
       │           │  chat_sessions   │       │  chat_messages    │
       │           │──────────────────│       │───────────────────│
       ├──────────▶│ id (PK)         │◀─────┤│ id (PK)          │
       │     1:N   │ company_id (FK) │   1:N │ session_id (FK)  │
       │           │ title           │       │ role             │
       │           │ created_at      │       │ content          │
       │           │ updated_at      │       │ sources (JSONB)  │
       │           └─────────────────┘       │ token_count      │
       │                                      │ created_at       │
       │                                      └──────────────────┘
       │
       │
       │           ┌──────────────────┐       ┌───────────────────┐
       │           │analysis_profiles │       │analysis_criteria  │
       │           │──────────────────│       │───────────────────│
       │           │ id (PK)         │◀─────┤│ id (PK)          │
       │           │ name            │   1:N │ profile_id (FK)  │
       │           │ description     │       │ name             │
       │           │ is_default      │       │ category         │
       │           │ created_at      │       │ description      │
       │           │ updated_at      │       │ formula          │
       │           └──────┬──────────┘       │ comparison       │
       │                  │                  │ threshold_value  │
       │                  │                  │ threshold_low    │
       │                  │                  │ threshold_high   │
       │                  │                  │ weight           │
       │                  │                  │ lookback_years   │
       │                  │                  │ enabled          │
       │                  │                  │ sort_order       │
       │                  │                  └──────────────────┘
       │                  │
       │                  │
       │           ┌──────┴───────────┐
       │           │analysis_results  │
       │           │──────────────────│
       ├──────────▶│ id (PK)         │
             1:N   │ company_id (FK) │
                   │ profile_id (FK) │
                   │ run_at          │
                   │ overall_score   │
                   │ max_score       │
                   │ pct_score       │
                   │ result_details  │
                   │   (JSONB)       │
                   │ summary         │
                   └─────────────────┘

7.2 Complete DDL

-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Enum Types
-- ============================================================
CREATE TYPE doc_type_enum AS ENUM ('10-K', '10-Q', '8-K', '20-F', 'DEF14A', 'OTHER');
CREATE TYPE doc_status_enum AS ENUM ('uploaded', 'parsing', 'parsed', 'embedding', 'ready', 'error');
CREATE TYPE criteria_category_enum AS ENUM (
    'profitability', 'valuation', 'growth', 'liquidity',
    'solvency', 'efficiency', 'dividend', 'quality', 'custom'
);
CREATE TYPE comparison_op_enum AS ENUM (
    '>', '>=', '<', '<=', '=', 'between', 'trend_up', 'trend_down'
);

-- ============================================================
-- Companies
-- ============================================================
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    cik             VARCHAR(20),
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    description     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_companies_ticker UNIQUE (ticker)
);

CREATE INDEX idx_companies_cik ON companies(cik) WHERE cik IS NOT NULL;

-- ============================================================
-- Documents
-- ============================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    doc_type        doc_type_enum NOT NULL,
    fiscal_year     INT NOT NULL,
    fiscal_quarter  INT,
    filing_date     DATE NOT NULL,
    period_end_date DATE NOT NULL,
    sec_accession   VARCHAR(30),
    source_url      VARCHAR(500),
    storage_bucket  VARCHAR(100) NOT NULL DEFAULT 'filings',
    storage_key     VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    page_count      INT,
    status          doc_status_enum NOT NULL DEFAULT 'uploaded',
    error_message   TEXT,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_documents_period UNIQUE (company_id, doc_type, fiscal_year, fiscal_quarter),
    CONSTRAINT chk_quarter_range CHECK (fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4),
    CONSTRAINT chk_fiscal_year CHECK (fiscal_year BETWEEN 1990 AND 2100)
);

CREATE INDEX idx_documents_company ON documents(company_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_company_year ON documents(company_id, fiscal_year);

-- ============================================================
-- Document Sections
-- ============================================================
CREATE TABLE document_sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_key     VARCHAR(50) NOT NULL,
    section_title   VARCHAR(255),
    content_text    TEXT NOT NULL,
    page_start      INT,
    page_end        INT,
    char_count      INT NOT NULL DEFAULT 0,
    token_count     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_section_per_doc UNIQUE (document_id, section_key)
);

CREATE INDEX idx_sections_document ON document_sections(document_id);

-- ============================================================
-- Document Chunks (for vector search metadata tracking)
-- ============================================================
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id      UUID REFERENCES document_sections(id) ON DELETE SET NULL,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    char_count      INT NOT NULL DEFAULT 0,
    token_count     INT,
    embedding_model VARCHAR(100),
    vector_id       VARCHAR(200),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_chunk_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_company ON document_chunks(company_id);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector_id ON document_chunks(vector_id) WHERE vector_id IS NOT NULL;

-- ============================================================
-- Financial Statements
-- ============================================================
CREATE TABLE financial_statements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    fiscal_year     INT NOT NULL,
    fiscal_quarter  INT,
    period_end_date DATE NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    statement_data  JSONB NOT NULL,
    source          VARCHAR(50) NOT NULL DEFAULT 'xbrl_api',
    raw_xbrl_data   JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_financial_period UNIQUE (company_id, fiscal_year, fiscal_quarter),
    CONSTRAINT chk_fin_quarter CHECK (fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4)
);

CREATE INDEX idx_financials_company ON financial_statements(company_id);
CREATE INDEX idx_financials_company_year ON financial_statements(company_id, fiscal_year);

-- ============================================================
-- Analysis Profiles
-- ============================================================
CREATE TABLE analysis_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    is_default      BOOLEAN NOT NULL DEFAULT false,
    version         INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_profile_name UNIQUE (name)
);

-- ============================================================
-- Analysis Criteria
-- ============================================================
CREATE TABLE analysis_criteria (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES analysis_profiles(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    category        criteria_category_enum NOT NULL,
    description     TEXT,
    formula         VARCHAR(500) NOT NULL,
    is_custom_formula BOOLEAN NOT NULL DEFAULT false,
    comparison      comparison_op_enum NOT NULL,
    threshold_value NUMERIC(20, 6),
    threshold_low   NUMERIC(20, 6),
    threshold_high  NUMERIC(20, 6),
    weight          NUMERIC(10, 4) NOT NULL DEFAULT 1.0,
    lookback_years  INT NOT NULL DEFAULT 5,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_weight_positive CHECK (weight > 0),
    CONSTRAINT chk_lookback_positive CHECK (lookback_years > 0 AND lookback_years <= 20),
    CONSTRAINT chk_threshold_between CHECK (
        comparison != 'between' OR (threshold_low IS NOT NULL AND threshold_high IS NOT NULL)
    ),
    CONSTRAINT chk_threshold_single CHECK (
        comparison IN ('between', 'trend_up', 'trend_down') OR threshold_value IS NOT NULL
    )
);

CREATE INDEX idx_criteria_profile ON analysis_criteria(profile_id);

-- ============================================================
-- Analysis Results
-- ============================================================
CREATE TABLE analysis_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    profile_id      UUID NOT NULL REFERENCES analysis_profiles(id) ON DELETE CASCADE,
    profile_version INT NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    overall_score   NUMERIC(10, 4) NOT NULL DEFAULT 0,
    max_score       NUMERIC(10, 4) NOT NULL DEFAULT 0,
    pct_score       NUMERIC(5, 2) NOT NULL DEFAULT 0,
    criteria_count  INT NOT NULL DEFAULT 0,
    passed_count    INT NOT NULL DEFAULT 0,
    failed_count    INT NOT NULL DEFAULT 0,
    result_details  JSONB NOT NULL DEFAULT '[]',
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_results_company ON analysis_results(company_id);
CREATE INDEX idx_results_profile ON analysis_results(profile_id);
CREATE INDEX idx_results_company_profile ON analysis_results(company_id, profile_id);
CREATE INDEX idx_results_run_at ON analysis_results(run_at DESC);

-- ============================================================
-- Chat Sessions
-- ============================================================
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    message_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_company ON chat_sessions(company_id);
CREATE INDEX idx_sessions_updated ON chat_sessions(updated_at DESC);

-- ============================================================
-- Chat Messages
-- ============================================================
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    sources         JSONB,
    token_count     INT,
    model_used      VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);

-- ============================================================
-- Utility: updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_financials_updated_at BEFORE UPDATE ON financial_statements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON analysis_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


7.3 Financial Statement Data Schema (JSONB)
The statement_data JSONB column in financial_statements follows this schema:

{
  "income_statement": {
    "revenue": 394328000000,                   // Total revenue / net sales
    "cost_of_revenue": 223546000000,           // COGS
    "gross_profit": 170782000000,              // Revenue - COGS
    "research_and_development": 29915000000,   // R&D expense
    "selling_general_admin": 24932000000,      // SG&A expense
    "operating_expenses": 54847000000,         // Total opex
    "operating_income": 115935000000,          // EBIT proxy
    "interest_expense": 3933000000,            // Interest expense
    "interest_income": 3999000000,             // Interest income
    "other_income_expense": 66000000,          // Other non-operating
    "income_before_tax": 116001000000,         // Pre-tax income
    "income_tax_expense": 19006000000,         // Tax provision
    "net_income": 96995000000,                 // Net income
    "eps_basic": 6.16,                         // Basic EPS
    "eps_diluted": 6.13,                       // Diluted EPS
    "shares_outstanding_basic": 15744231000,   // Basic share count
    "shares_outstanding_diluted": 15812547000, // Diluted share count
    "ebitda": null,                            // Computed if depreciation available
    "depreciation_amortization": 11519000000   // D&A
  },
  "balance_sheet": {
    "cash_and_equivalents": 29965000000,
    "short_term_investments": 35228000000,
    "accounts_receivable": 60932000000,
    "inventory": 6331000000,
    "total_current_assets": 143566000000,
    "property_plant_equipment": 43715000000,   // Net PP&E
    "goodwill": 0,
    "intangible_assets": 0,
    "long_term_investments": 100544000000,
    "total_assets": 352583000000,
    "accounts_payable": 62611000000,
    "short_term_debt": 15807000000,            // Current portion of debt
    "total_current_liabilities": 153982000000,
    "long_term_debt": 98959000000,
    "total_liabilities": 290437000000,
    "common_stock": 73812000000,               // Common stock + APIC
    "retained_earnings": -214000000,
    "treasury_stock": 0,
    "total_equity": 62146000000,
    "book_value_per_share": null               // Computed: equity / shares
  },
  "cash_flow": {
    "operating_cash_flow": 110543000000,       // CFO
    "depreciation_in_cfo": 11519000000,        // D&A in CFO
    "stock_based_compensation": 10833000000,   // SBC in CFO
    "capital_expenditure": -10959000000,       // CapEx (negative)
    "acquisitions": 0,                         // M&A spend
    "investment_purchases": -29513000000,      // Investment buys
    "investment_sales": 29917000000,           // Investment sells
    "investing_cash_flow": -7077000000,        // CFI
    "debt_issued": 0,
    "debt_repaid": -11151000000,
    "dividends_paid": -14841000000,
    "share_buybacks": -77550000000,            // Share repurchases
    "financing_cash_flow": -103362000000,      // CFF
    "free_cash_flow": 99584000000,             // CFO + CapEx
    "net_change_in_cash": 104000000
  }
}

7.4 Vector Store Schema (Qdrant)

# Collection naming: company_{company_id}  (one collection per company)
# Each collection uses HNSW index for fast approximate nearest neighbor search

collection_config:
  vectors:
    size: 3072           # OpenAI text-embedding-3-large dimension
    distance: Cosine     # Cosine similarity
  hnsw_config:
    m: 16                # HNSW graph connections
    ef_construct: 100    # Construction search breadth
  optimizers_config:
    indexing_threshold: 20000  # Trigger optimization at 20k vectors
  on_disk_payload: true        # Store payloads on disk (large text content)

# Point (vector) payload schema:
point_payload:
  text: string              # Original chunk text (for retrieval display)
  company_id: string        # UUID
  document_id: string       # UUID
  doc_type: string          # "10-K", "10-Q"
  fiscal_year: integer
  fiscal_quarter: integer   # nullable
  section_key: string       # "item_1a", "item_7", etc.
  section_title: string     # "Risk Factors", "MD&A", etc.
  filing_date: string       # ISO date
  period_end_date: string   # ISO date
  chunk_index: integer      # Position within document
  token_count: integer

# Payload indexes (for filtered search):
payload_indexes:
  - field: doc_type
    type: keyword
  - field: fiscal_year
    type: integer
  - field: section_key
    type: keyword


8. API Specification
8.1 General Conventions

base_url: /api/v1
content_type: application/json
authentication: X-API-Key header
pagination: offset/limit with Link headers
error_format:
  status: integer
  error: string
  message: string
  details: object (optional)
date_format: ISO 8601 (YYYY-MM-DD)
datetime_format: ISO 8601 with timezone (YYYY-MM-DDTHH:mm:ssZ)
id_format: UUID v4

8.2 Endpoints
8.2.1 Companies

POST /api/v1/companies:
  description: Register a new company
  request_body:
    ticker: string (required, 1-10 chars, uppercase)
    name: string (optional — auto-resolved from SEC if omitted)
    cik: string (optional — auto-resolved from ticker)
    sector: string (optional)
    industry: string (optional)
  response: 201 Created
    body: Company object
  errors:
    409: Ticker already exists
    422: Validation error
    502: SEC EDGAR unreachable (if auto-resolving)

GET /api/v1/companies:
  description: List all companies
  query_params:
    search: string (filter by ticker or name, case-insensitive)
    sector: string (filter by sector)
    sort_by: string (ticker|name|created_at, default: ticker)
    sort_order: string (asc|desc, default: asc)
    limit: integer (1-100, default: 50)
    offset: integer (default: 0)
  response: 200 OK
    body:
      items: Company[] (with doc_count, latest_filing_date, readiness_pct)
      total: integer
      limit: integer
      offset: integer

GET /api/v1/companies/{company_id}:
  description: Get company details
  response: 200 OK
    body: Company object with:
      documents_summary:
        total: integer
        by_status: {ready: N, processing: N, error: N}
        by_type: {"10-K": N, "10-Q": N}
        year_range: {min: YYYY, max: YYYY}
      financials_summary:
        periods_available: integer
        year_range: {min: YYYY, max: YYYY}
      recent_sessions: ChatSession[] (last 5)
  errors:
    404: Company not found

PUT /api/v1/companies/{company_id}:
  description: Update company metadata
  request_body: (partial update, all fields optional)
    name: string
    sector: string
    industry: string
    description: string
  response: 200 OK
  errors:
    404: Company not found

DELETE /api/v1/companies/{company_id}:
  description: Delete company and ALL associated data
  query_params:
    confirm: boolean (required, must be true)
  response: 204 No Content
  errors:
    404: Company not found
    400: confirm=true not provided


8.2.2 Documents

POST /api/v1/companies/{company_id}/documents:
  description: Upload a filing document
  content_type: multipart/form-data
  request_body:
    file: binary (required, PDF or HTML, max 50MB)
    doc_type: string (required, enum: 10-K, 10-Q, 8-K)
    fiscal_year: integer (required, 1990-2100)
    fiscal_quarter: integer (optional, 1-4, required for 10-Q)
    filing_date: date (required, ISO format)
    period_end_date: date (required, ISO format)
    sec_accession: string (optional)
    source_url: string (optional)
  response: 202 Accepted
    body:
      document_id: UUID
      status: "uploaded"
      message: "Document uploaded and queued for processing"
  errors:
    404: Company not found
    409: Document for this period already exists
    413: File too large
    415: Unsupported file type
    422: Validation error

POST /api/v1/companies/{company_id}/documents/fetch-sec:
  description: Auto-fetch filings from SEC EDGAR
  request_body:
    filing_types: string[] (default: ["10-K", "10-Q"])
    years_back: integer (default: 10, max: 30)
  response: 202 Accepted
    body:
      task_id: UUID
      message: "Fetching filings from SEC EDGAR"
      estimated_filings: integer
  errors:
    404: Company not found
    400: Company has no CIK
    429: Too many concurrent fetch operations

GET /api/v1/companies/{company_id}/documents:
  description: List documents for a company
  query_params:
    doc_type: string (filter)
    fiscal_year: integer (filter)
    status: string (filter)
    sort_by: string (fiscal_year|filing_date|created_at, default: fiscal_year)
    sort_order: string (asc|desc, default: desc)
    limit: integer (default: 50)
    offset: integer (default: 0)
  response: 200 OK
    body:
      items: Document[]
      total: integer

GET /api/v1/companies/{company_id}/documents/{document_id}:
  description: Get document details with section list
  response: 200 OK
    body: Document with:
      sections: Section[] (section_key, title, token_count)
      chunk_count: integer
      financial_data_extracted: boolean

POST /api/v1/companies/{company_id}/documents/{document_id}/retry:
  description: Retry failed ingestion
  response: 202 Accepted
  errors:
    404: Document not found
    400: Document not in error state

DELETE /api/v1/companies/{company_id}/documents/{document_id}:
  description: Delete document and all derived data
  query_params:
    confirm: boolean (required)
  response: 204 No Content

8.2.3 Chat

POST /api/v1/companies/{company_id}/chat:
  description: Send a message and receive streaming AI response
  request_body:
    message: string (required, 1-10000 chars)
    session_id: UUID (optional — creates new session if omitted)
    retrieval_config: (optional)
      top_k: integer (1-50, default: 15)
      score_threshold: float (0-1, default: 0.65)
      filter_doc_types: string[] (optional, e.g., ["10-K"])
      filter_year_min: integer (optional)
      filter_year_max: integer (optional)
      filter_sections: string[] (optional, e.g., ["item_1a", "item_7"])
  response: 200 OK (text/event-stream)
    SSE events:
      event: session
      data: {"session_id": "UUID", "title": "..."}

      event: sources
      data: {"sources": [{"chunk_id": "...", "doc_type": "10-K", "fiscal_year": 2024, ...}]}

      event: token
      data: {"token": "The"}

      event: token
      data: {"token": " company"}

      event: done
      data: {"message_id": "UUID", "token_count": 523}

      event: error
      data: {"error": "...", "message": "..."}
  errors:
    404: Company not found
    400: No documents ready for this company
    429: Rate limit exceeded

GET /api/v1/companies/{company_id}/chat/sessions:
  description: List chat sessions for a company
  query_params:
    limit: integer (default: 20)
    offset: integer (default: 0)
  response: 200 OK
    body:
      items: ChatSession[] (id, title, message_count, created_at, updated_at)
      total: integer

GET /api/v1/companies/{company_id}/chat/sessions/{session_id}:
  description: Get full chat history
  response: 200 OK
    body:
      session: ChatSession
      messages: ChatMessage[] (role, content, sources, created_at)

DELETE /api/v1/companies/{company_id}/chat/sessions/{session_id}:
  description: Delete a chat session and all messages
  response: 204 No Content

8.2.4 Analysis

POST /api/v1/analysis/profiles:
  description: Create an analysis profile
  request_body:
    name: string (required, unique)
    description: string (optional)
    is_default: boolean (default: false)
    criteria: (required, array, 1-30 items)
      - name: string (required)
        category: string (required, enum)
        description: string (optional)
        formula: string (required — built-in name or custom expression)
        is_custom_formula: boolean (default: false)
        comparison: string (required, enum)
        threshold_value: number (conditional)
        threshold_low: number (conditional)
        threshold_high: number (conditional)
        weight: number (default: 1.0, > 0)
        lookback_years: integer (default: 5, 1-20)
        enabled: boolean (default: true)
        sort_order: integer (default: 0)
  response: 201 Created
  errors:
    409: Profile name already exists
    422: Validation error (invalid formula, missing threshold, etc.)

GET /api/v1/analysis/profiles:
  description: List all analysis profiles
  response: 200 OK

GET /api/v1/analysis/profiles/{profile_id}:
  description: Get profile with all criteria
  response: 200 OK

PUT /api/v1/analysis/profiles/{profile_id}:
  description: Update profile (increments version)
  request_body: same as POST
  response: 200 OK

DELETE /api/v1/analysis/profiles/{profile_id}:
  description: Delete profile and criteria (results are preserved with snapshot)
  response: 204 No Content

POST /api/v1/analysis/run:
  description: Run analysis for company/companies against a profile
  request_body:
    company_ids: UUID[] (required, 1-10)
    profile_id: UUID (required)
    generate_summary: boolean (default: true)
  response: 200 OK
    body:
      results: AnalysisResult[] (one per company)
        - company_id: UUID
          company_ticker: string
          company_name: string
          overall_score: number
          max_score: number
          pct_score: number
          passed_count: integer
          failed_count: integer
          criteria_results: CriteriaResult[]
            - criteria_name: string
              category: string
              formula: string
              values_by_year: {2020: 0.42, 2021: 0.44, ...}
              latest_value: number
              threshold: string (human-readable, e.g., ">= 0.15")
              passed: boolean
              weighted_score: number
              trend: string
              note: string
          summary: string (AI-generated)
  errors:
    404: Company or profile not found
    400: No financial data available for company

GET /api/v1/analysis/results:
  description: List past analysis results
  query_params:
    company_id: UUID (optional filter)
    profile_id: UUID (optional filter)
    limit: integer (default: 20)
    offset: integer (default: 0)
  response: 200 OK

GET /api/v1/analysis/results/{result_id}:
  description: Get a specific analysis result
  response: 200 OK

GET /api/v1/analysis/formulas:
  description: List all available built-in formulas
  response: 200 OK
    body:
      formulas:
        - name: string
          category: string
          description: string
          required_fields: string[]
          example: string

8.2.5 Financial Data

GET /api/v1/companies/{company_id}/financials:
  description: Get structured financial data
  query_params:
    period: string (annual|quarterly|all, default: annual)
    start_year: integer (optional)
    end_year: integer (optional)
  response: 200 OK
    body:
      company_id: UUID
      periods: FinancialPeriod[]
        - fiscal_year: integer
          fiscal_quarter: integer (null for annual)
          period_end_date: date
          income_statement: {}
          balance_sheet: {}
          cash_flow: {}

GET /api/v1/companies/{company_id}/financials/export:
  description: Export financial data as CSV
  query_params:
    period: string (default: annual)
    start_year: integer (optional)
    end_year: integer (optional)
  response: 200 OK (text/csv)
    headers:
      Content-Disposition: attachment; filename="AAPL_financials.csv"

8.2.6 System

GET /api/v1/health:
  description: Health check
  response: 200 OK
    body:
      status: "healthy"
      components:
        database: "healthy" | "unhealthy"
        vector_store: "healthy" | "unhealthy"
        object_storage: "healthy" | "unhealthy"
        redis: "healthy" | "unhealthy"
        llm_api: "healthy" | "unhealthy"
      version: "1.0.0"
      uptime_seconds: integer

GET /api/v1/tasks/{task_id}:
  description: Check async task status (SEC fetch, bulk operations)
  response: 200 OK
    body:
      task_id: UUID
      status: "pending" | "running" | "completed" | "failed"
      progress: {current: N, total: N, message: string}
      result: object (when completed)
      error: string (when failed)

9. Ingestion Pipeline
9.1 Pipeline Stages

┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                            │
│                                                                  │
│  Stage 1          Stage 2          Stage 3         Stage 4       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐   ┌──────────┐   │
│  │ PARSE    │───▶│ SPLIT    │───▶│ EXTRACT  │──▶│ EMBED    │   │
│  │          │    │ SECTIONS │    │ FINANCIALS│   │          │   │
│  │ PDF→text │    │          │    │ (XBRL)   │   │ chunk    │   │
│  │ HTML→text│    │ Item 1   │    │          │   │ embed    │   │
│  │          │    │ Item 1A  │    │ income   │   │ store    │   │
│  │          │    │ Item 7   │    │ balance  │   │          │   │
│  │          │    │ Item 8   │    │ cashflow │   │          │   │
│  │          │    │ ...      │    │          │   │          │   │
│  └──────────┘    └──────────┘    └──────────┘   └──────────┘   │
│                                                                  │
│  Status:          Status:         (parallel)     Status:         │
│  uploaded→parsing parsing→parsed                 parsed→embedding│
│                                                  →ready          │
└─────────────────────────────────────────────────────────────────┘

9.2 Document Parsing Rules

| Format | Parser | Notes |
| :-- | :-- | :-- |
| PDF | PyMuPDF (fitz) | Extract text page by page. Preserve paragraph breaks. Handle multi-column layouts. |
| HTML | BeautifulSoup + custom cleaner | Strip tags, normalize whitespace, preserve table structure as markdown, handle SEC-specific HTML quirks (nested tables, inline styles). |

Cleaning rules:

Remove page headers/footers (page numbers, repeating company name)
Normalize Unicode (smart quotes → straight quotes, em-dashes → hyphens)
Collapse multiple blank lines to single blank line
Remove table of contents pages (detect by pattern of dotted leaders + page numbers)
Preserve table data as pipe-delimited markdown tables
Remove image alt-text and figure references
9.3 Section Splitting Rules
10-K Sections:
| Section Key | Pattern (regex) | Significance |
| :-- | :-- | :-- |
| item_1 | Item\s+1[.\s].*Business | Company description, products, markets |
| item_1a | Item\s+1A[.\s].*Risk\s+Factors | Key business and market risks |
| item_1b | Item\s+1B[.\s].*Unresolved | SEC staff comments |
| item_1c | Item\s+1C[.\s].*Cyber | Cybersecurity (new, post-2023) |
| item_2 | Item\s+2[.\s].*Properties | Physical assets |
| item_3 | Item\s+3[.\s].*Legal | Litigation |
| item_5 | Item\s+5[.\s].*Market | Stock info, dividends |
| item_6 | Item\s+6[.\s].*(?:Selected|Reserved) | Historical selected data (now reserved) |
| item_7 | Item\s+7[.\s].*Management | MD&A — most important narrative section |
| item_7a | Item\s+7A[.\s].*Quantitative | Market risk disclosures |
| item_8 | Item\s+8[.\s].*Financial\s+Statements | Full financial statements + notes |
| item_9a | Item\s+9A[.\s].*Controls | Internal controls |

Disambiguation strategy: When a section header appears multiple times (e.g., in table of contents AND actual section), take the LAST occurrence, as the TOC typically comes first.

10-Q Sections follow Part I / Part II structure with a subset of items.

9.4 Chunking Strategy
chunking_config:
  method: recursive_character_text_splitter
  chunk_size: 768        # target tokens per chunk
  chunk_overlap: 128     # overlap tokens between consecutive chunks
  length_function: tiktoken (cl100k_base encoding)
  separators:            # split priority (try first separator, then next)
    - "\n\n\n"           # section break
    - "\n\n"             # paragraph break
    - "\n"               # line break
    - ". "               # sentence break
    - " "                # word break (last resort)
  metadata_attached:
    - company_id
    - document_id
    - doc_type
    - fiscal_year
    - fiscal_quarter
    - section_key
    - section_title
    - filing_date
    - period_end_date
    - chunk_index
    - token_count

9.5 Financial Data Extraction
Primary source: SEC EDGAR XBRL companyfacts API

Endpoint: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json
Returns ALL historical XBRL-tagged financial data for a company
One API call gets all years and quarters
XBRL Tag Mapping (see Appendix B for complete mapping of 60+ tags)

Fallback: If XBRL data is insufficient (older filings, foreign issuers), the system should:

Log a warning indicating which fields are missing
Store whatever is available
Not block the rest of the ingestion pipeline

9.6 Embedding Configuration

embedding:
  model: text-embedding-3-large      # OpenAI
  dimensions: 3072
  batch_size: 64                      # chunks per API call
  max_retries: 3
  retry_delay: 1.0                    # seconds, with exponential backoff
  rate_limit: 3000                    # requests per minute (OpenAI tier)

# Alternative models (configurable):
#  model: text-embedding-3-small     # 1536 dims, cheaper
#  model: text-embedding-ada-002     # legacy, 1536 dims

10. RAG Chat Agent
10.1 System Prompt
You are a financial analyst assistant specialized in analyzing public company 
SEC filings. You are currently focused on {company_name} (ticker: {ticker}, 
CIK: {cik}).

You have access to SEC filings spanning from {earliest_year} to {latest_year}.
Available filing types: {available_doc_types}.
Total filings indexed: {total_documents}.

## Your Rules

1. **Ground every answer in the provided filing excerpts.** Do not use external 
   knowledge about the company. If the provided context doesn't contain the 
   answer, say: "I don't have enough information in the indexed filings to 
   answer this question."

2. **Always cite your sources.** When referencing information, include the 
   filing type, fiscal year, quarter (if applicable), and section. Example: 
   "According to the FY2023 10-K, Item 1A (Risk Factors)..."

3. **Be precise with numbers.** When quoting financial figures, include the 
   exact number from the filing and the period it refers to. Never estimate 
   or round figures from filings.

4. **Compare across periods when relevant.** If the user asks about changes 
   or trends, reference multiple filings to show how things evolved.

5. **Distinguish facts from analysis.** Clearly separate what the filing 
   states (fact) from your analytical interpretation of that information.

6. **Refuse out-of-scope requests.** Do not:
   - Predict future performance or stock prices
   - Give buy/sell/hold recommendations
   - Compare with other companies (unless their filings are also indexed)
   - Answer questions unrelated to the company's SEC filings
   
   Instead, politely explain your scope and suggest how to rephrase.

7. **Handle ambiguity.** If a question could refer to multiple periods or 
   topics, ask for clarification or answer for the most recent period while 
   noting the ambiguity.

8. **Format for readability.** Use markdown formatting: headers for sections, 
   bullet points for lists, bold for emphasis, tables for comparative data.

10.2 Retrieval Configuration

retrieval:
  default_top_k: 15                    # number of chunks to retrieve
  max_top_k: 50
  default_score_threshold: 0.65        # minimum similarity score (cosine)
  reranking: false                     # V1: no reranking; V2 consideration
  
  # Query expansion (optional, improves recall):
  query_expansion:
    enabled: true
    method: llm_expansion
    prompt: |
      Given the user's question about a company's SEC filings, generate 
      2-3 alternative search queries that would help find relevant 
      information. Focus on SEC filing terminology and section names.
      
      User question: {question}
      
      Alternative queries (one per line):

  # Context window management:
  context_budget:
    max_context_tokens: 12000          # max tokens for retrieved context
    max_history_tokens: 4000           # max tokens for conversation history
    max_response_tokens: 4096          # max tokens for LLM response

10.3 Prompt Construction

Messages sent to LLM:

[0] system: {system_prompt}           # Company-specific system prompt

[1] user: (historical message 1)       # Conversation history
[2] assistant: (historical response 1) # (last N exchanges)
[...] 

[N] user:                              # Current message with context
    ## Retrieved Filing Excerpts
    
    [Source 1: 10-K FY2024, Item 1A — Risk Factors | relevance: 0.89]
    {chunk_text_1}
    
    ---
    
    [Source 2: 10-K FY2023, Item 7 — MD&A | relevance: 0.85]
    {chunk_text_2}
    
    ---
    
    [Source 3: 10-Q FY2024 Q2, Part I Item 2 | relevance: 0.78]
    {chunk_text_3}
    
    ... (up to top_k sources)
    
    ## User Question
    
    {user_message}

10.4 LLM Configuration

llm:
  provider: openai                # openai | anthropic
  model: gpt-4o                  # primary model
  fallback_model: gpt-4o-mini    # if primary fails or for cost savings
  temperature: 0.2                # low temp for factual accuracy
  max_tokens: 4096
  streaming: true
  timeout: 120                    # seconds
  
  # Cost control:
  max_monthly_spend: null         # optional dollar limit
  log_token_usage: true           # track tokens per message for cost monitoring

11. Financial Analysis Engine
11.1 Built-in Formula Registry
See Appendix A for the complete list of 25+ built-in formulas.

11.2 Custom Formula DSL
# Custom formula expression syntax:

# Field references (dot notation into statement_data):
#   income_statement.revenue
#   balance_sheet.total_assets
#   cash_flow.operating_cash_flow

# Previous period reference:
#   prev(income_statement.revenue)     # same field, previous year

# Operators: + - * / ( )
# Functions: abs(x), min(x, y), max(x, y)

# Examples:
custom_formulas:
  - name: "Piotroski F-Score Component: ROA Positive"
    expression: "income_statement.net_income > 0"
    # Returns 1 if true, 0 if false

  - name: "Custom ROIC"  
    expression: >
      income_statement.operating_income * (1 - 0.21) / 
      (balance_sheet.total_assets - balance_sheet.total_current_liabilities - balance_sheet.cash_and_equivalents)

  - name: "Revenue CAGR 3Y"
    expression: >
      (income_statement.revenue / prev(income_statement.revenue, 3)) ^ (1/3) - 1

  - name: "Capex to Revenue"
    expression: >
      abs(cash_flow.capital_expenditure) / income_statement.revenue

11.3 Expression Parser Specification

expression_parser:
  supported_operators: ["+", "-", "*", "/", "^", ">", ">=", "<", "<="]
  supported_functions:
    abs: {args: 1, description: "Absolute value"}
    min: {args: 2, description: "Minimum of two values"}
    max: {args: 2, description: "Maximum of two values"}
    avg: {args: "variadic", description: "Average of values"}
  
  field_reference_pattern: "(income_statement|balance_sheet|cash_flow)\\.[a-z_]+"
  prev_reference_pattern: "prev\\((.+?)(?:,\\s*(\\d+))?\\)"
  
  validation_rules:
    - All field references must correspond to known financial data fields
    - Division by zero must be handled (return null)
    - prev() lookback must not exceed available data
    - Parentheses must be balanced
    - Expression must return a numeric value
  
  error_messages:
    unknown_field: "Unknown financial field: '{field}'. Available fields: ..."
    division_by_zero: "Division by zero encountered for period {year}"
    unbalanced_parens: "Unbalanced parentheses in expression"
    syntax_error: "Syntax error at position {pos}: {detail}"

11.4 Trend Detection Algorithm

# Algorithm: Ordinary Least Squares (OLS) linear regression
# Input: dict of {year: value} with at least 3 non-null values
# Output: "improving" | "declining" | "stable"

def detect_trend(values_by_year: dict[int, float | None]) -> str:
    valid = [(y, v) for y, v in sorted(values_by_year.items()) if v is not None]
    if len(valid) < 3:
        return "insufficient_data"
    
    years = np.array([v[0] for v in valid], dtype=float)
    vals = np.array([v[1] for v in valid], dtype=float)
    
    # Center years to reduce numerical issues
    year_mean = years.mean()
    years_centered = years - year_mean
    
    # OLS slope
    slope = np.sum(years_centered * vals) / np.sum(years_centered ** 2)
    
    # Normalize slope by mean absolute value of the metric
    mean_abs = np.mean(np.abs(vals))
    if mean_abs < 1e-10:
        return "stable"
    
    relative_slope = slope / mean_abs
    
    # Thresholds:
    #   > +3% relative annual change → improving
    #   < -3% relative annual change → declining
    #   otherwise → stable
    if relative_slope > 0.03:
        return "improving"
    elif relative_slope < -0.03:
        return "declining"
    else:
        return "stable"

11.5 Scoring Rules

scoring:
  # Each criterion produces a binary score (0 or 1)
  # multiplied by its weight to produce weighted_score
  # Overall score = sum(weighted_scores)
  # Max score = sum(weights of enabled criteria)
  # Percentage = overall_score / max_score * 100

  pass_rules:
    ">":         latest_value > threshold_value
    ">=":        latest_value >= threshold_value
    "<":         latest_value < threshold_value
    "<=":        latest_value <= threshold_value
    "=":         abs(latest_value - threshold_value) < 0.001
    "between":   threshold_low <= latest_value <= threshold_high
    "trend_up":  trend == "improving"
    "trend_down": trend == "declining"

  null_handling:
    # If latest_value is null (formula couldn't compute):
    - criterion is marked as "no_data" (not pass or fail)
    - it does NOT count toward max_score
    - a note is added explaining which financial fields were missing

  percentage_grading:
    "A":  90-100%
    "B":  75-89%
    "C":  60-74%
    "D":  40-59%
    "F":  0-39%

12. Frontend Specification
12.1 Page Structure

┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (persistent)         │  MAIN CONTENT                   │
│                               │                                  │
│  ┌─────────────────────────┐  │  ┌──────────────────────────┐   │
│  │ 🏠 Dashboard            │  │  │  PAGE CONTENT            │   │
│  │ 🏢 Companies            │  │  │  (varies by route)       │   │
│  │   ├── AAPL              │  │  │                          │   │
│  │   ├── MSFT              │  │  │                          │   │
│  │   ├── GOOGL             │  │  │                          │   │
│  │   └── + Add Company     │  │  │                          │   │
│  │ 📊 Analysis Profiles    │  │  │                          │   │
│  │ ⚙️ Settings             │  │  │                          │   │
│  └─────────────────────────┘  │  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

12.2 Key Pages

pages:
  /dashboard:
    description: Overview of all companies with quick stats
    components:
      - CompanyGrid (cards showing ticker, name, doc count, readiness, last analysis score)
      - QuickActions (add company, run analysis)
      - RecentActivity (latest chats, uploads, analyses)

  /companies:
    description: Company list with search and filters
    components:
      - SearchBar
      - CompanyTable (sortable, filterable)
      - AddCompanyModal

  /companies/{id}:
    description: Company detail page with tabs
    tabs:
      overview:
        - CompanyHeader (ticker, name, sector, CIK)
        - FilingSummaryCard (doc count by type and status)
        - FinancialSummaryCard (latest key metrics)
        - RecentChatSessions
      documents:
        - DocumentTimeline (visual timeline of filings)
        - DocumentTable (all filings with status, actions)
        - UploadButton → UploadModal
        - FetchFromSECButton → FetchModal
      financials:
        - PeriodSelector (annual/quarterly, year range)
        - FinancialDataTable (pivoted: metrics as rows, periods as columns)
        - MetricCharts (line charts for key metrics over time)
        - ExportCSVButton
      chat:
        - ChatSessionList (sidebar within tab)
        - ChatInterface (message list + input)
        - SourcesPanel (collapsible, shows retrieved chunks)
      analysis:
        - ProfileSelector (dropdown)
        - RunAnalysisButton
        - ScoreCard (overall score, grade, pass/fail counts)
        - CriteriaTable (all criteria with values, thresholds, status)
        - TrendCharts (per-criterion historical chart)
        - AISummary (expandable narrative)
        - HistoricalResults (past analysis runs)

  /analysis/profiles:
    description: Manage analysis profiles
    components:
      - ProfileList
      - ProfileEditor
        - CriteriaBuilder (add/edit/remove/reorder criteria)
        - FormulaSelector (built-in dropdown + custom expression editor)
        - ThresholdInput (adapts to comparison type)
        - WeightSlider
        - PreviewButton (dry run against a sample company)

  /analysis/compare:
    description: Multi-company comparison
    components:
      - CompanySelector (multi-select)
      - ProfileSelector
      - ComparisonTable (companies as columns, criteria as rows)
      - RankingChart (bar chart of overall scores)

  /settings:
    description: System configuration
    components:
      - LLMSettings (model, temperature, API key status)
      - EmbeddingSettings (model, dimensions)
      - IngestionSettings (chunk size, overlap)
      - APIKeyManagement

12.3 Chat Interface Specification

chat_interface:
  layout:
    left_panel: (30% width, collapsible)
      - SessionList (grouped by date: today, this week, older)
      - NewChatButton
    main_panel: (70% width)
      - MessageList (scrollable, auto-scroll on new tokens)
        - UserMessage: right-aligned, blue bubble
        - AssistantMessage: left-aligned, white bubble, markdown rendered
        - SourcesAccordion: collapsible below assistant message
          - SourceChip: "📄 10-K FY2024 Item 1A (89%)" — clickable
          - SourceDetail: shows chunk text when expanded
      - InputArea (bottom, sticky)
        - TextArea (auto-resize, shift+enter for newlines, enter to send)
        - SendButton
        - RetrievalConfigToggle (expandable panel for top_k, filters)
  
  streaming_behavior:
    - Show typing indicator ("● ● ●") while waiting for first token
    - Render tokens as they arrive (append to message)
    - Parse markdown incrementally (render complete blocks)
    - Show sources after full response is received
    - Enable copy button on completed messages
    - Show token count on completed messages

  error_handling:
    - If SSE connection drops: show "Connection lost. Retry?" with button
    - If LLM returns error: show error message in red banner, preserve input
    - If no sources found: show info banner "No relevant filings found"

13. Technology Stack
13.1 Backend

| Component | Technology | Version | Justification |
| :-- | :-- | :-- | :-- |
| Language | Python | 3.12+ | Rich ML/AI ecosystem, async support |
| API Framework | FastAPI | 0.110+ | Async, auto-docs, Pydantic validation, SSE support |
| ASGI Server | Uvicorn | 0.29+ | Production-grade ASGI server |
| ORM | SQLAlchemy | 2.0+ | Async support, type-safe queries, mature ecosystem |
| Migrations | Alembic | 1.13+ | Standard for SQLAlchemy, versioned migrations |
| Task Queue | Celery | 5.3+ | Mature, reliable async task processing |
| Task Broker | Redis | 7+ | Celery broker + caching + rate limiting |
| HTTP Client | httpx | 0.27+ | Async HTTP for SEC API, LLM calls |
| PDF Parser | PyMuPDF (fitz) | 1.24+ | Fast, reliable PDF text extraction |
| HTML Parser | BeautifulSoup4 | 4.12+ | Standard HTML parsing |
| Tokenizer | tiktoken | 0.7+ | OpenAI tokenizer for accurate chunk sizing |
| LLM Client | openai (Python SDK) | 1.30+ | Official SDK, streaming support |
| Vector Client | qdrant-client | 1.9+ | Official Qdrant SDK, async support |
| S3 Client | boto3 / aioboto3 | 1.34+ | S3/MinIO compatible |
| Validation | Pydantic | 2.7+ | Data validation, serialization |
| Testing | pytest + pytest-asyncio | 8.0+ | Standard Python testing |
| Linting | Ruff | 0.4+ | Fast Python linter/formatter |
| Type Checking | mypy | 1.10+ | Static type checking |

13.2 Frontend

| Component | Technology | Version | Justification |
| :-- | :-- | :-- | :-- |
| Framework | Next.js | 14+ | React SSR, App Router, API routes |
| Language | TypeScript | 5.4+ | Type safety |
| UI Library | shadcn/ui | latest | High-quality, customizable components |
| Styling | Tailwind CSS | 3.4+ | Utility-first, consistent design |
| Charts | Recharts | 2.12+ | React-native charting, simple API |
| State | React Query (TanStack) | 5+ | Server state management, caching |
| Forms | React Hook Form + Zod | latest | Form validation |
| Markdown | react-markdown | 9+ | Render LLM responses |
| SSE | eventsource-parser | latest | Parse SSE streams |
| HTTP | ky or fetch | latest | API calls |
| Testing | Vitest + React Testing Library | latest | Component testing |

13.3 Data Infrastructure

| Component | Technology | Version | Justification |
| :-- | :-- | :-- | :-- |
| Relational DB | PostgreSQL | 16+ | JSONB, robust, extensible |
| Vector DB | Qdrant | 1.9+ | Purpose-built vector search, payload filtering, collections |
| Object Storage | MinIO | latest | S3-compatible, self-hosted |
| Cache/Broker | Redis | 7+ | Celery broker, caching, rate limiting |

13.4 External Services

| Service | Purpose | Required |
| :-- | :-- | :-- |
| OpenAI API | Embeddings (text-embedding-3-large) + Chat (gpt-4o) | Yes |
| SEC EDGAR API | Company info, filing index, XBRL data | Yes (free, no key needed) |
| Anthropic API | Alternative LLM (Claude) | No (optional) |

14. Infrastructure & Deployment
14.1 Docker Compose (Development & Single-Server Production)

# docker-compose.yml

version: "3.9"

services:
  # ── APPLICATION SERVICES ──────────────────────────────────

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      uvicorn app.main:app 
      --host 0.0.0.0 
      --port 8000 
      --workers 4 
      --loop uvloop
    ports:
      - "${API_PORT:-8000}:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    volumes:
      - ./backend:/app        # dev only, remove for production
    restart: unless-stopped

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      celery -A app.worker.celery_app worker
      --loglevel=info
      --concurrency=${WORKER_CONCURRENCY:-4}
      --queues=ingestion,analysis,sec_fetch
      --max-tasks-per-child=50
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
      minio:
        condition: service_healthy
    volumes:
      - ./backend:/app        # dev only
    restart: unless-stopped

  worker-monitor:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      celery -A app.worker.celery_app flower
      --port=5555
      --broker_api=redis://redis:6379/0
    ports:
      - "${FLOWER_PORT:-5555}:5555"
    env_file: .env
    depends_on:
      - redis
    restart: unless-stopped
    profiles: ["monitoring"]     # only start with --profile monitoring

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "${FRONTEND_PORT:-3000}:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api
    restart: unless-stopped

  # ── DATA SERVICES ─────────────────────────────────────────

  postgres:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      POSTGRES_DB: ${DB_NAME:-company_analysis}
      POSTGRES_USER: ${DB_USER:-analyst}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
    ports:
      - "${DB_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-analyst} -d ${DB_NAME:-company_analysis}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.9.7
    volumes:
      - qdrant_data:/qdrant/storage
      - qdrant_snapshots:/qdrant/snapshots
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
      QDRANT__SERVICE__HTTP_PORT: 6333
    ports:
      - "${QDRANT_HTTP_PORT:-6333}:6333"
      - "${QDRANT_GRPC_PORT:-6334}:6334"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Create default bucket on startup
  minio-setup:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 $${MINIO_ACCESS_KEY} $${MINIO_SECRET_KEY};
      mc mb --ignore-existing local/filings;
      mc mb --ignore-existing local/exports;
      exit 0;
      "
    environment:
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:?required}

volumes:
  pgdata:
  qdrant_data:
  qdrant_snapshots:
  redis_data:
  minio_data:

  14.2 Backend Dockerfile

  FROM python:3.12-slim AS base

# System dependencies for PyMuPDF and other native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

14.3 Frontend Dockerfile

FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]

14.4 Resource Requirements

minimum_resources:
  development:
    cpu: 4 cores
    ram: 8 GB
    disk: 20 GB
  production_small:    # up to 50 companies
    cpu: 4 cores
    ram: 16 GB
    disk: 100 GB (SSD recommended)
  production_medium:   # up to 200 companies
    cpu: 8 cores
    ram: 32 GB
    disk: 500 GB SSD

per_service_allocation:
  api:         { cpu: "1.0", memory: "1Gi" }
  worker:      { cpu: "2.0", memory: "4Gi" }    # PDF parsing is memory-intensive
  postgres:    { cpu: "1.0", memory: "2Gi" }
  qdrant:      { cpu: "1.0", memory: "4Gi" }    # vectors in memory
  redis:       { cpu: "0.25", memory: "256Mi" }
  minio:       { cpu: "0.5", memory: "512Mi" }
  frontend:    { cpu: "0.25", memory: "256Mi" }

14.5 Backup Strategy

backups:
  postgresql:
    method: pg_dump
    schedule: daily at 02:00 UTC
    retention: 30 days
    command: >
      pg_dump -U analyst -d company_analysis 
      --format=custom 
      --file=/backups/pg_$(date +%Y%m%d_%H%M%S).dump

  qdrant:
    method: snapshot API
    schedule: daily at 03:00 UTC
    retention: 14 days
    command: >
      curl -X POST "http://qdrant:6333/collections/{name}/snapshots"

  minio:
    method: mc mirror
    schedule: daily at 04:00 UTC
    retention: 30 days
    command: >
      mc mirror local/filings /backups/minio/filings/

  strategy_notes:
    - Postgres backup is most critical (all metadata, financial data, chat history)
    - Qdrant can be rebuilt from chunks in Postgres (re-embed), but backup is faster
    - MinIO stores original files; losing these means re-downloading from SEC
    - All backups should be stored on a separate volume or remote storage

15. Security
15.1 Authentication (V1)

authentication:
  method: API Key
  header: X-API-Key
  storage: environment variable (API_KEY)
  validation: constant-time string comparison
  
  # API key is set during deployment via .env
  # All API endpoints except /health require valid API key
  # Frontend embeds API key in requests (acceptable for single-user self-hosted)
  
  # Future (V2): JWT with user accounts, OAuth2

15.2 Input Validation

input_validation:
  file_upload:
    max_size: 50MB (configurable via MAX_UPLOAD_SIZE_MB)
    allowed_types: 
      - application/pdf
      - text/html
      - application/xhtml+xml
    validation: check magic bytes, not just Content-Type header
    filename_sanitization: strip path components, limit to alphanumeric + dots + hyphens

  text_input:
    max_chat_message_length: 10000 characters
    max_company_name_length: 255 characters
    max_formula_expression_length: 500 characters
    sql_injection: handled by SQLAlchemy parameterized queries
    xss: React auto-escapes output; markdown renderer uses allowlist

  numeric_input:
    fiscal_year: 1990-2100
    fiscal_quarter: 1-4 or null
    weight: > 0, <= 100
    lookback_years: 1-20
    threshold values: -999999999 to 999999999

15.3 LLM Prompt Security

prompt_security:
  - User message is ALWAYS placed in the designated user content section
  - User message NEVER appears in the system prompt
  - System prompt is hardcoded server-side (not user-modifiable)
  - Retrieved context is clearly delimited from user input in the prompt
  - The agent is instructed to refuse off-topic requests
  - No tool-use / function-calling that could access system resources

16. Testing Strategy
16.1 Testing Pyramid

                    ┌─────────────┐
                    │   E2E (5%)  │    Playwright / Cypress
                    │   Tests     │    Critical user journeys
                    ├─────────────┤
                 ┌──┤ Integration │    pytest + testcontainers
                 │  │  Tests (25%)│    API → DB → Vector Store
                 │  ├─────────────┤
              ┌──┤  │   Unit      │    pytest + pytest-asyncio
              │  │  │  Tests (70%)│    Pure logic, mocked deps
              │  │  └─────────────┘
              │  │
              └──┘

16.2 Unit Tests

unit_tests:
  framework: pytest + pytest-asyncio
  mocking: unittest.mock / pytest-mock
  coverage_target: 85% line coverage minimum
  
  test_areas:

    # ── Section Splitter ──────────────────────────
    section_splitter:
      test_files: tests/unit/test_section_splitter.py
      tests:
        - test_split_10k_all_sections_present:
            input: sample 10-K full text with all 15 items
            expected: 15 Section objects with correct keys and content
        - test_split_10k_missing_sections:
            input: 10-K missing Items 6 and 9B
            expected: 13 sections, missing ones not in output
        - test_split_handles_table_of_contents_duplicates:
            input: 10-K where Item 1A appears in TOC and body
            expected: section starts at body occurrence, not TOC
        - test_split_10q_sections:
            input: sample 10-Q text
            expected: correct Part I / Part II section split
        - test_split_unknown_doc_type_returns_full_text:
            input: doc_type="OTHER", any text
            expected: single section with full text
        - test_section_content_is_trimmed:
            expected: no leading/trailing whitespace in section content
        - test_section_key_format:
            expected: all section_keys match pattern item_[0-9]+[a-z]?

    # ── Text Chunker ──────────────────────────────
    chunker:
      test_files: tests/unit/test_chunker.py
      tests:
        - test_chunk_short_text_returns_single_chunk:
            input: text with 100 tokens
            expected: 1 chunk, content == input
        - test_chunk_long_text_returns_multiple_chunks:
            input: text with 3000 tokens
            expected: ~4-5 chunks of ~768 tokens each
        - test_chunk_overlap_content:
            input: text with 2000 tokens, overlap=128
            expected: end of chunk N overlaps with start of chunk N+1
        - test_chunk_preserves_paragraph_boundaries:
            input: text with clear paragraph breaks
            expected: chunks break at paragraph boundaries when possible
        - test_chunk_metadata_propagation:
            input: text with metadata dict
            expected: all chunks carry the same metadata
        - test_chunk_token_count_accuracy:
            expected: reported token_count matches tiktoken encoding
        - test_empty_text_returns_empty_list:
            input: ""
            expected: []

    # ── Financial Formulas ────────────────────────
    formulas:
      test_files: tests/unit/test_formulas.py
      tests:
        - test_gross_margin_calculation:
            input: {revenue: 100M, gross_profit: 40M}
            expected: 0.40
        - test_gross_margin_zero_revenue:
            input: {revenue: 0, gross_profit: 0}
            expected: None
        - test_roe_calculation:
            input: {net_income: 10M, total_equity: 50M}
            expected: 0.20
        - test_roe_negative_equity:
            input: {net_income: 10M, total_equity: -5M}
            expected: -2.0 (valid, indicates issue)
        - test_debt_to_equity:
            input: {long_term_debt: 30M, total_equity: 60M}
            expected: 0.50
        - test_

    # ── Financial Formulas (continued) ────────────
    formulas:
      tests:
        - test_debt_to_equity_zero_equity:
            input: {long_term_debt: 30M, total_equity: 0}
            expected: None (division by zero handled)
        - test_current_ratio:
            input: {total_current_assets: 80M, total_current_liabilities: 40M}
            expected: 2.0
        - test_free_cash_flow_margin:
            input: {operating_cash_flow: 50M, capital_expenditure: -10M, revenue: 200M}
            expected: 0.20
        - test_revenue_growth_rate:
            input: {revenue_current: 120M, revenue_prior: 100M}
            expected: 0.20
        - test_revenue_growth_rate_prior_zero:
            input: {revenue_current: 120M, revenue_prior: 0}
            expected: None
        - test_all_builtin_formulas_registered:
            expected: FormulaRegistry contains at least 25 entries
        - test_formula_registry_get_unknown_formula:
            input: formula_name="nonexistent"
            expected: raises FormulaNotFoundError
        - test_formula_required_fields_documented:
            expected: every registered formula declares required_fields list
        - test_roic_calculation:
            input: {operating_income: 25M, total_assets: 200M, current_liabilities: 50M, cash: 20M}
            expected: 25M * (1-0.21) / (200M - 50M - 20M) ≈ 0.1519
        - test_interest_coverage_ratio:
            input: {operating_income: 30M, interest_expense: 5M}
            expected: 6.0
        - test_interest_coverage_zero_interest:
            input: {operating_income: 30M, interest_expense: 0}
            expected: None (or Infinity — define behavior as None)

    # ── Custom Formula Parser ─────────────────────
    formula_parser:
      test_files: tests/unit/test_formula_parser.py
      tests:
        - test_parse_simple_division:
            input: "income_statement.net_income / balance_sheet.total_equity"
            expected: AST with Division node, two FieldRef leaves
        - test_parse_nested_parentheses:
            input: "(a + b) * (c - d)"
            expected: correct operator precedence in AST
        - test_parse_function_call_abs:
            input: "abs(cash_flow.capital_expenditure)"
            expected: AST with FunctionCall(abs, [FieldRef])
        - test_parse_prev_reference:
            input: "prev(income_statement.revenue)"
            expected: PrevRef node with lookback=1
        - test_parse_prev_reference_with_lookback:
            input: "prev(income_statement.revenue, 3)"
            expected: PrevRef node with lookback=3
        - test_parse_complex_expression:
            input: "(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)"
            expected: valid AST computing YoY revenue growth
        - test_parse_invalid_field_name:
            input: "nonexistent_statement.foo / bar"
            expected: raises FormulaParseError with field error
        - test_parse_unbalanced_parentheses:
            input: "(a + b * c"
            expected: raises FormulaParseError mentioning parentheses
        - test_parse_empty_expression:
            input: ""
            expected: raises FormulaParseError
        - test_parse_division_by_literal_zero:
            input: "income_statement.revenue / 0"
            expected: raises FormulaParseError or returns null at eval time
        - test_evaluate_simple_expression:
            input: expression="income_statement.revenue * 0.5", data={revenue: 100M}
            expected: 50M
        - test_evaluate_with_missing_field:
            input: expression referencing field not in data
            expected: None (not crash)
        - test_evaluate_prev_with_prior_data:
            input: current={revenue: 120M}, prior={revenue: 100M}
            expected: prev(revenue) resolves to 100M
        - test_evaluate_prev_without_prior_data:
            input: current={revenue: 120M}, prior=None
            expected: None

    # ── Trend Detection ───────────────────────────
    trend_detection:
      test_files: tests/unit/test_trend_detection.py
      tests:
        - test_strong_upward_trend:
            input: {2020: 10, 2021: 15, 2022: 20, 2023: 25, 2024: 30}
            expected: "improving"
        - test_strong_downward_trend:
            input: {2020: 30, 2021: 25, 2022: 20, 2023: 15, 2024: 10}
            expected: "declining"
        - test_stable_values:
            input: {2020: 10.0, 2021: 10.1, 2022: 9.9, 2023: 10.0, 2024: 10.2}
            expected: "stable"
        - test_insufficient_data_points:
            input: {2023: 10, 2024: 12}
            expected: "insufficient_data"
        - test_all_null_values:
            input: {2020: None, 2021: None, 2022: None}
            expected: "insufficient_data"
        - test_mixed_null_values:
            input: {2020: 10, 2021: None, 2022: 15, 2023: None, 2024: 20}
            expected: "improving" (nulls ignored, 3 valid points)
        - test_single_data_point:
            input: {2024: 42}
            expected: "insufficient_data"
        - test_negative_values_declining:
            input: {2020: -5, 2021: -10, 2022: -15, 2023: -20}
            expected: "declining" (values getting more negative)
        - test_volatile_but_flat:
            input: {2020: 10, 2021: 20, 2022: 5, 2023: 25, 2024: 10}
            expected: "stable" (no clear directional trend)

    # ── Threshold Evaluator ───────────────────────
    threshold_evaluator:
      test_files: tests/unit/test_threshold_evaluator.py
      tests:
        - test_greater_than_pass:
            input: {value: 0.20, comparison: ">", threshold: 0.15}
            expected: passed=True
        - test_greater_than_fail:
            input: {value: 0.10, comparison: ">", threshold: 0.15}
            expected: passed=False
        - test_greater_than_equal_boundary:
            input: {value: 0.15, comparison: ">=", threshold: 0.15}
            expected: passed=True
        - test_less_than:
            input: {value: 0.30, comparison: "<", threshold: 0.50}
            expected: passed=True
        - test_between_inclusive:
            input: {value: 0.25, comparison: "between", low: 0.20, high: 0.30}
            expected: passed=True
        - test_between_at_boundary:
            input: {value: 0.20, comparison: "between", low: 0.20, high: 0.30}
            expected: passed=True
        - test_between_outside:
            input: {value: 0.35, comparison: "between", low: 0.20, high: 0.30}
            expected: passed=False
        - test_trend_up_with_improving:
            input: {trend: "improving", comparison: "trend_up"}
            expected: passed=True
        - test_trend_up_with_declining:
            input: {trend: "declining", comparison: "trend_up"}
            expected: passed=False
        - test_trend_up_with_stable:
            input: {trend: "stable", comparison: "trend_up"}
            expected: passed=False
        - test_null_value:
            input: {value: None, comparison: ">", threshold: 0.15}
            expected: passed=None, note="no_data"

    # ── Scoring Engine ────────────────────────────
    scoring:
      test_files: tests/unit/test_scoring.py
      tests:
        - test_all_criteria_pass:
            input: 5 criteria, all pass, weights=[1,1,1,1,1]
            expected: score=5, max=5, pct=100.0
        - test_all_criteria_fail:
            input: 5 criteria, all fail, weights=[1,1,1,1,1]
            expected: score=0, max=5, pct=0.0
        - test_mixed_pass_fail:
            input: 3 pass, 2 fail, weights=[1,2,1,2,1]
            expected: score=4, max=7, pct≈57.14
        - test_weighted_scoring:
            input: criterion A (weight=3, pass), criterion B (weight=1, fail)
            expected: score=3, max=4, pct=75.0
        - test_no_data_excluded_from_max:
            input: 3 criteria, 2 pass, 1 no_data
            expected: max=2 (not 3), score=2, pct=100.0
        - test_all_no_data:
            input: 3 criteria, all no_data
            expected: max=0, score=0, pct=0 (or "N/A")
        - test_disabled_criteria_excluded:
            input: 3 criteria, 1 disabled
            expected: only 2 criteria evaluated
        - test_grade_assignment:
            expected: 95→A, 80→B, 65→C, 45→D, 30→F

    # ── Document Parser ───────────────────────────
    document_parser:
      test_files: tests/unit/test_document_parser.py
      tests:
        - test_parse_simple_pdf:
            input: fixtures/simple_10k.pdf
            expected: extracted text length > 0, paragraphs preserved
        - test_parse_html_filing:
            input: fixtures/sample_10k.html
            expected: clean text, tables converted to markdown
        - test_parse_html_strips_style_tags:
            input: HTML with <style> and <script> blocks
            expected: no CSS or JS in output
        - test_parse_html_preserves_tables:
            input: HTML with financial data tables
            expected: pipe-delimited markdown table in output
        - test_clean_text_normalizes_whitespace:
            input: text with \xa0, multiple spaces, \r\n
            expected: normalized to standard spaces and \n
        - test_clean_text_removes_page_numbers:
            input: text with "Page 42 of 215" patterns
            expected: page number lines removed
        - test_unsupported_format_raises_error:
            input: file.docx
            expected: raises UnsupportedFormatError

    # ── XBRL Data Mapper ──────────────────────────
    xbrl_mapper:
      test_files: tests/unit/test_xbrl_mapper.py
      tests:
        - test_map_revenue_tag:
            input: XBRL tag "us-gaap:Revenues" with value 394328000000
            expected: maps to income_statement.revenue
        - test_map_alternative_revenue_tag:
            input: XBRL tag "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
            expected: maps to income_statement.revenue (alternative tag)
        - test_map_balance_sheet_tags:
            input: fixture of XBRL balance sheet tags
            expected: all key balance_sheet fields populated
        - test_handle_unknown_tag:
            input: XBRL tag "us-gaap:SomeObscureTag"
            expected: ignored (not in mapping), no error
        - test_select_correct_period:
            input: XBRL facts with multiple period values
            expected: selects annual (12 month) or quarterly (3 month) correctly
        - test_handle_missing_required_tags:
            input: XBRL data missing revenue
            expected: income_statement.revenue = None, warning logged
        - test_full_company_facts_parsing:
            input: fixtures/apple_companyfacts_sample.json
            expected: multiple years of complete financial data

    # ── SEC EDGAR Client ──────────────────────────
    sec_client:
      test_files: tests/unit/test_sec_client.py
      tests:
        - test_resolve_cik_from_ticker:
            input: "AAPL" (mocked response)
            expected: CIK="0000320193"
        - test_resolve_unknown_ticker:
            input: "XYZNOTREAL"
            expected: raises TickerNotFoundError
        - test_get_filing_index:
            input: CIK, filing_type="10-K", count=10
            expected: list of filing metadata dicts
        - test_rate_limiting_applied:
            expected: requests spaced at least 100ms apart
        - test_user_agent_header_set:
            expected: all requests include User-Agent with email

    # ── Chat Prompt Builder ───────────────────────
    prompt_builder:
      test_files: tests/unit/test_prompt_builder.py
      tests:
        - test_system_prompt_contains_company_info:
            input: company={ticker: "AAPL", name: "Apple Inc"}
            expected: system prompt contains "Apple Inc" and "AAPL"
        - test_system_prompt_contains_filing_range:
            input: earliest_year=2015, latest_year=2024
            expected: system prompt mentions 2015 and 2024
        - test_context_injection_format:
            input: 3 retrieved chunks with metadata
            expected: formatted with source headers and separator lines
        - test_context_token_budget_respected:
            input: 30 chunks totaling 50000 tokens, budget=12000
            expected: only top chunks fitting within 12000 tokens included
        - test_history_included_in_messages:
            input: 5 previous exchanges
            expected: messages array includes all 10 messages (5 user + 5 assistant)
        - test_history_truncation:
            input: 20 previous exchanges, max_history=10
            expected: only last 10 exchanges included
        - test_empty_context_produces_no_context_message:
            input: 0 retrieved chunks
            expected: message includes note about no relevant filings found

16.3 Integration Tests

integration_tests:
  framework: pytest + testcontainers (Docker-based)
  environment:
    postgres: testcontainers postgres:16-alpine
    qdrant: testcontainers qdrant/qdrant:v1.9.7
    redis: testcontainers redis:7-alpine
    minio: testcontainers minio/minio:latest
    llm_api: mocked via httpx respx or VCR.py
    sec_api: mocked via httpx respx with recorded fixtures

  fixtures:
    sample_companies:
      - ticker: "TEST", name: "Test Corp", cik: "0001234567"
      - ticker: "SMPL", name: "Sample Inc", cik: "0009876543"
    sample_documents:
      - fixtures/test_corp_10k_2024.pdf (10 pages, all sections)
      - fixtures/test_corp_10k_2023.pdf
      - fixtures/test_corp_10q_2024_q1.html
    sample_xbrl:
      - fixtures/test_corp_companyfacts.json
    sample_embeddings:
      - pre-computed embedding vectors for test chunks
      - deterministic (not calling OpenAI in tests)

  test_suites:

    # ── Company API Integration ───────────────────
    company_api:
      test_files: tests/integration/test_company_api.py
      setup: clean database
      tests:
        - test_create_company_success:
            action: POST /api/v1/companies {"ticker": "TEST"}
            expected:
              status: 201
              body: contains id, ticker="TEST", name populated
              db: companies table has 1 row
        - test_create_company_duplicate_ticker:
            setup: create company TEST
            action: POST /api/v1/companies {"ticker": "TEST"}
            expected: status 409
        - test_list_companies_empty:
            action: GET /api/v1/companies
            expected: status 200, items=[], total=0
        - test_list_companies_with_data:
            setup: create 3 companies
            action: GET /api/v1/companies
            expected: status 200, total=3
        - test_list_companies_search:
            setup: create AAPL, MSFT, GOOGL
            action: GET /api/v1/companies?search=app
            expected: returns only AAPL
        - test_get_company_detail:
            setup: create company, upload 2 documents
            action: GET /api/v1/companies/{id}
            expected: includes documents_summary with total=2
        - test_get_company_not_found:
            action: GET /api/v1/companies/{random_uuid}
            expected: status 404
        - test_delete_company_cascades:
            setup: create company with documents, chunks, financials, chat sessions
            action: DELETE /api/v1/companies/{id}?confirm=true
            expected:
              status: 204
              db: no rows in any table referencing this company
              qdrant: collection deleted
              minio: files removed
        - test_delete_company_without_confirm:
            action: DELETE /api/v1/companies/{id}
            expected: status 400

    # ── Document Upload Integration ───────────────
    document_api:
      test_files: tests/integration/test_document_api.py
      tests:
        - test_upload_pdf_document:
            setup: create company
            action: POST /api/v1/companies/{id}/documents (multipart with PDF)
            expected:
              status: 202
              body: document_id present, status="uploaded"
              minio: file exists at expected key
              db: documents row with status="uploaded"
        - test_upload_html_document:
            action: POST with HTML file
            expected: same as PDF test
        - test_upload_duplicate_period:
            setup: upload 10-K FY2024
            action: upload another 10-K FY2024
            expected: status 409
        - test_upload_oversized_file:
            action: POST with 60MB file
            expected: status 413
        - test_upload_invalid_file_type:
            action: POST with .docx file
            expected: status 415
        - test_list_documents_for_company:
            setup: upload 5 documents for company A, 3 for company B
            action: GET /api/v1/companies/{A}/documents
            expected: returns exactly 5
        - test_list_documents_filter_by_type:
            setup: upload 3 10-Ks and 2 10-Qs
            action: GET /api/v1/companies/{id}/documents?doc_type=10-K
            expected: returns 3
        - test_delete_document_removes_chunks:
            setup: upload and fully process a document
            action: DELETE /api/v1/companies/{id}/documents/{doc_id}?confirm=true
            expected:
              db: no chunks for this document
              qdrant: vectors removed from collection
              minio: file removed

    # ── Ingestion Pipeline Integration ────────────
    ingestion_pipeline:
      test_files: tests/integration/test_ingestion_pipeline.py
      note: >
        These tests run the actual pipeline against real (test fixture) files.
        OpenAI embedding calls are mocked with deterministic vectors.
      tests:
        - test_full_ingestion_pdf:
            setup: create company, upload PDF fixture
            action: run ingestion pipeline synchronously (bypass Celery)
            expected:
              db: document status = "ready"
              db: document_sections has >= 5 rows
              db: document_chunks has >= 20 rows
              qdrant: collection exists with vectors matching chunk count
        - test_full_ingestion_html:
            setup: create company, upload HTML fixture
            expected: same as PDF
        - test_ingestion_creates_financial_data:
            setup: create company with CIK, upload 10-K
            action: run ingestion with XBRL extraction (mocked SEC API)
            expected:
              db: financial_statements has 1 row for this period
              data: income_statement, balance_sheet, cash_flow populated
        - test_ingestion_idempotent:
            setup: fully process a document
            action: re-run ingestion for same document
            expected: no duplicate chunks, same vector count in Qdrant
        - test_ingestion_failure_marks_error:
            setup: upload corrupt PDF
            action: run ingestion
            expected:
              db: document status = "error"
              db: error_message contains meaningful description
        - test_ingestion_retry_after_failure:
            setup: document in error state
            action: POST /retry endpoint, then run ingestion with fixed mock
            expected: document status = "ready"
        - test_section_splitting_accuracy:
            setup: upload fixture 10-K with known sections
            action: run ingestion
            expected: sections match expected section_keys from fixture
        - test_chunk_overlap_verification:
            setup: process document
            expected: |
              for consecutive chunks in same section:
                last 128 tokens of chunk[i] == first 128 tokens of chunk[i+1]

    # ── Chat Integration ──────────────────────────
    chat_api:
      test_files: tests/integration/test_chat_api.py
      note: >
        LLM responses are mocked via httpx respx to return predetermined
        streaming responses. Vector search uses real Qdrant with test data.
      setup:
        - Create company
        - Process 2 test documents (10-K FY2023, 10-K FY2024)
        - Pre-loaded chunks in Qdrant with test embeddings
      tests:
        - test_create_new_chat_session:
            action: POST /api/v1/companies/{id}/chat {"message": "What does the company do?"}
            expected:
              SSE events include: session, sources, token(s), done
              db: chat_sessions has 1 row
              db: chat_messages has 2 rows (user + assistant)
        - test_chat_returns_sources:
            action: POST /chat with question about risk factors
            expected:
              sources event contains chunks from item_1a sections
              each source has doc_type, fiscal_year, section_key, relevance_score
        - test_chat_continues_existing_session:
            setup: create session with 1 exchange
            action: POST /chat with session_id, new message
            expected:
              db: session now has 4 messages (2 user + 2 assistant)
              same session_id returned
        - test_chat_filters_by_doc_type:
            action: POST /chat with filter_doc_types=["10-K"]
            expected: all sources are from 10-K documents
        - test_chat_filters_by_year:
            action: POST /chat with filter_year_min=2024, filter_year_max=2024
            expected: all sources are from FY2024
        - test_chat_with_no_ready_documents:
            setup: company with 0 processed documents
            action: POST /chat
            expected: status 400, message about no documents
        - test_chat_session_list:
            setup: create 3 sessions
            action: GET /chat/sessions
            expected: 3 sessions, ordered by updated_at desc
        - test_chat_session_history:
            setup: session with 5 exchanges
            action: GET /chat/sessions/{id}
            expected: 10 messages in chronological order
        - test_delete_chat_session:
            setup: session with messages
            action: DELETE /chat/sessions/{id}
            expected: status 204, session and messages gone

    # ── Analysis Integration ──────────────────────
    analysis_api:
      test_files: tests/integration/test_analysis_api.py
      setup:
        - Create company with financial_statements for FY2020-FY2024
        - Create analysis profile with 5 criteria
      tests:
        - test_create_analysis_profile:
            action: POST /analysis/profiles with 5 criteria
            expected:
              status: 201
              db: profile + 5 criteria rows
        - test_create_profile_invalid_formula:
            action: POST with formula="nonexistent_formula"
            expected: status 422 with error about unknown formula
        - test_create_profile_invalid_custom_formula:
            action: POST with custom expression "income_statement.foo / bar"
            expected: status 422 with error about unknown field
        - test_run_analysis:
            action: POST /analysis/run {company_ids: [...], profile_id: ...}
            expected:
              status: 200
              body: results with overall_score, criteria_results array
              each criterion has values_by_year, latest_value, passed, trend
              db: analysis_results has 1 row
        - test_run_analysis_all_criteria_computable:
            setup: company with complete financial data
            expected: no "no_data" criteria results
        - test_run_analysis_missing_financial_data:
            setup: company with only 1 year of data
            expected:
              trend = "insufficient_data" for all criteria
              criteria still evaluated on available data
        - test_run_analysis_multi_company:
            setup: 3 companies with financial data
            action: POST /run with 3 company_ids
            expected: 3 result objects, each independently scored
        - test_analysis_results_persistence:
            action: run analysis, then GET /analysis/results?company_id=X
            expected: previous result retrievable
        - test_update_profile_increments_version:
            action: PUT /profiles/{id} with modified criteria
            expected: version incremented, old results preserve old version number
        - test_list_builtin_formulas:
            action: GET /analysis/formulas
            expected: at least 25 formulas with name, category, description, required_fields

    # ── Financial Data Integration ────────────────
    financials_api:
      test_files: tests/integration/test_financials_api.py
      tests:
        - test_get_annual_financials:
            setup: company with 5 years of annual data
            action: GET /companies/{id}/financials?period=annual
            expected: 5 period objects with income_statement, balance_sheet, cash_flow
        - test_get_quarterly_financials:
            setup: company with quarterly data
            action: GET /companies/{id}/financials?period=quarterly
            expected: quarterly periods returned
        - test_filter_by_year_range:
            action: GET /financials?start_year=2022&end_year=2024
            expected: only periods within 2022-2024
        - test_export_csv:
            action: GET /companies/{id}/financials/export
            expected:
              content-type: text/csv
              CSV parseable with correct headers
              values match database

    # ── Cross-Cutting Integration ─────────────────
    auth:
      test_files: tests/integration/test_auth.py
      tests:
        - test_valid_api_key:
            action: any endpoint with correct X-API-Key header
            expected: request succeeds (200/201/202)
        - test_missing_api_key:
            action: GET /companies with no X-API-Key header
            expected: status 401
        - test_invalid_api_key:
            action: GET /companies with X-API-Key="wrong"
            expected: status 401
        - test_health_endpoint_no_auth:
            action: GET /health with no API key
            expected: status 200 (health is public)

    health_check:
      test_files: tests/integration/test_health.py
      tests:
        - test_all_healthy:
            expected: status 200, all components "healthy"
        - test_database_down:
            setup: stop postgres container
            expected: database component shows "unhealthy", overall still returns 200
        - test_qdrant_down:
            setup: stop qdrant container
            expected: vector_store shows "unhealthy"

16.4 End-to-End Tests

e2e_tests:
  framework: Playwright (Python or TypeScript)
  browser: Chromium
  environment: full docker-compose stack with mocked external APIs
  
  note: >
    E2E tests cover critical user journeys through the actual UI.
    LLM and SEC APIs are mocked at the network level (mock server).
    Tests use realistic but small fixture files.

  test_suites:

    # ── Journey 1: Complete Company Setup ─────────
    test_company_setup_journey:
      file: tests/e2e/test_company_journey.py
      steps:
        1. Navigate to /companies
        2. Click "Add Company"
        3. Enter ticker "TEST" in modal
        4. Submit → company created, redirected to company page
        5. Verify company header shows "Test Corp" (auto-resolved name)
        6. Navigate to Documents tab
        7. Click "Fetch from SEC"
        8. Select "10-K" and "Last 2 years"
        9. Submit → progress indicator shows
        10. Wait for all documents to reach "ready" status (poll)
        11. Navigate to Financials tab
        12. Verify financial data table shows 2 years of data
      assertions:
        - Company appears in sidebar after creation
        - Documents tab shows correct filing count
        - Financial data is populated for expected periods
      timeout: 120s (ingestion is slow even with mocks)

    # ── Journey 2: Manual Upload & Chat ───────────
    test_upload_and_chat_journey:
      file: tests/e2e/test_upload_chat_journey.py
      setup: company "TEST" already exists
      steps:
        1. Navigate to /companies/{TEST}/documents
        2. Click "Upload Document"
        3. Select fixture PDF, fill metadata (10-K, FY2024, etc.)
        4. Submit → file uploads, processing begins
        5. Wait for status = "ready" (poll or observe status change)
        6. Navigate to Chat tab
        7. Click "New Chat"
        8. Type "What are the main risk factors?"
        9. Press Enter or click Send
        10. Observe streaming response appearing token by token
        11. Verify response contains filing citation
        12. Expand sources section → verify source chips
        13. Click on a source chip → see chunk text
        14. Type follow-up: "How have these changed from last year?"
        15. Observe response references multiple filing years
        16. Navigate away and come back → session is preserved
        17. Open session → full history visible
      assertions:
        - Streaming works (text appears progressively)
        - Citations reference correct document type and year
        - Sources panel shows relevant sections
        - Session persists across page navigation
        - Chat history loads correctly

    # ── Journey 3: Analysis Workflow ──────────────
    test_analysis_journey:
      file: tests/e2e/test_analysis_journey.py
      setup: company "TEST" with 3 years of financial data
      steps:
        1. Navigate to /analysis/profiles
        2. Click "Create Profile"
        3. Name: "My Value Screen"
        4. Add criterion: Gross Margin > 40%, weight 2, category profitability
        5. Add criterion: Debt to Equity < 0.5, weight 1, category solvency
        6. Add criterion: ROE > 15%, weight 3, category profitability
        7. Save profile
        8. Navigate to /companies/{TEST}/analysis
        9. Select "My Value Screen" profile
        10. Click "Run Analysis"
        11. Loading spinner appears
        12. Results load: score card, criteria table, AI summary
        13. Verify score card shows overall percentage and grade
        14. Verify criteria table shows values, thresholds, pass/fail coloring
        15. Click on a criterion → trend chart appears
        16. Scroll to AI summary → verify narrative is present
      assertions:
        - Profile creation succeeds with validation
        - Analysis runs and produces scored results
        - Pass/fail colors are correct (green/red)
        - Trend charts render with data points
        - AI summary mentions company name

    # ── Journey 4: Multi-Company Comparison ───────
    test_comparison_journey:
      file: tests/e2e/test_comparison_journey.py
      setup: 3 companies with financial data, 1 analysis profile
      steps:
        1. Navigate to /analysis/compare
        2. Select 3 companies from multi-select dropdown
        3. Select analysis profile
        4. Click "Compare"
        5. Comparison table loads with companies as columns
        6. Verify each criterion row shows values for each company
        7. Verify color coding (green for pass, red for fail)
        8. Verify companies are ranked by overall score
      assertions:
        - All 3 companies appear in comparison
        - Ranking is correct (highest score first)
        - Cell colors match pass/fail status

16.5 Performance Tests

performance_tests:
  framework: locust (Python-based load testing)
  target: API endpoints

  scenarios:

    test_ingestion_throughput:
      description: Measure how long it takes to process N documents
      method: submit 10 documents, measure time until all reach "ready"
      target: < 5 minutes per document average
      measurements:
        - total_time_seconds
        - avg_time_per_document
        - max_time_per_document
        - peak_memory_usage

    test_vector_search_latency:
      description: Measure vector search performance as collection grows
      method: pre-load Qdrant with N vectors, run 100 search queries
      scenarios:
        - 10K vectors:   target p50 < 50ms, p99 < 200ms
        - 100K vectors:  target p50 < 100ms, p99 < 300ms
        - 500K vectors:  target p50 < 200ms, p99 < 500ms
      measurements:
        - p50_latency_ms
        - p95_latency_ms
        - p99_latency_ms
        - queries_per_second

    test_analysis_computation:
      description: Measure analysis engine performance
      method: run analysis with 30 criteria over 10 years for 1 company
      target: < 3 seconds
      measurements:
        - total_time_ms
        - per_criterion_time_ms
        - formula_evaluation_time_ms

    test_concurrent_api_load:
      description: Simulate multiple browser tabs
      method: 10 concurrent users doing mixed operations
      target: p95 < 500ms for non-streaming endpoints
      operations:
        - list companies (30%)
        - get company detail (30%)
        - get financial data (20%)
        - list chat sessions (10%)
        - run analysis (10%)

16.6 Test Data & Fixtures

test_fixtures:
  directory: tests/fixtures/

  documents:
    simple_10k.pdf:
      description: 10-page synthetic 10-K with all standard sections
      content: lorem-ipsum style but with realistic section headers
      purpose: unit tests for parsing and splitting

    simple_10k.html:
      description: HTML version of simple 10-K
      content: same content as PDF but in SEC-style HTML with nested tables
      purpose: HTML parsing tests

    real_10k_excerpt.pdf:
      description: 20-page excerpt from a real (public domain) 10-K filing
      content: anonymized or from a well-known company
      purpose: realistic integration testing

    corrupt_file.pdf:
      description: Intentionally corrupt PDF
      purpose: error handling tests

    large_10k.pdf:
      description: 250-page realistic 10-K
      purpose: performance testing, chunking verification

  xbrl_data:
    companyfacts_complete.json:
      description: Complete SEC companyfacts API response
      content: 5 years of annual + quarterly data, all major XBRL tags
      purpose: XBRL mapping integration tests

    companyfacts_sparse.json:
      description: Partial companyfacts with missing tags
      purpose: testing graceful handling of missing data

  financial_data:
    test_financials_5y.json:
      description: 5 years of statement_data JSON (FY2020-FY2024)
      content: realistic values for a mid-cap tech company
      purpose: formula computation and analysis tests

  llm_responses:
    chat_response_risk_factors.json:
      description: Pre-recorded OpenAI streaming response about risk factors
      purpose: chat integration tests (mocked LLM)

    chat_response_revenue_segments.json:
      description: Pre-recorded response about revenue breakdown
      purpose: chat integration tests

    analysis_summary_response.json:
      description: Pre-recorded analysis narrative summary
      purpose: analysis integration tests

  embeddings:
    test_embeddings.npy:
      description: Pre-computed 3072-dim embeddings for test chunks
      content: 100 embedding vectors (deterministic, not from real model)
      purpose: vector search integration tests without calling OpenAI

  sec_api_responses:
    edgar_company_tickers.json:
      description: Mocked SEC company tickers lookup response
      purpose: CIK resolution tests

    edgar_submissions.json:
      description: Mocked SEC submissions API response (filing index)
      purpose: filing fetch tests

  generation_script:
    description: >
      A Python script (tests/fixtures/generate_fixtures.py) that generates
      all synthetic test fixtures deterministically. Run once to create,
      commit to repo. Allows regeneration if schema changes.

16.7 CI/CD Pipeline

ci_pipeline:
  platform: GitHub Actions (or equivalent)

  triggers:
    - push to main
    - pull request to main
    - manual trigger

  jobs:

    lint-and-typecheck:
      runs-on: ubuntu-latest
      steps:
        - checkout
        - setup python 3.12
        - install dependencies
        - run: ruff check backend/
        - run: ruff format --check backend/
        - run: mypy backend/app/ --strict
        - setup node 20
        - run: cd frontend && npm ci
        - run: cd frontend && npm run lint
        - run: cd frontend && npm run type-check

    unit-tests:
      runs-on: ubuntu-latest
      steps:
        - checkout
        - setup python 3.12
        - install dependencies
        - run: pytest tests/unit/ -v --cov=app --cov-report=xml --cov-fail-under=85
        - upload coverage report

    integration-tests:
      runs-on: ubuntu-latest
      services:
        postgres: postgres:16-alpine
        redis: redis:7-alpine
        qdrant: qdrant/qdrant:v1.9.7
        minio: minio/minio:latest
      steps:
        - checkout
        - setup python 3.12
        - install dependencies
        - run migrations
        - run: pytest tests/integration/ -v --timeout=120
      env:
        DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
        QDRANT_URL: http://localhost:6333
        REDIS_URL: redis://localhost:6379/0
        MINIO_ENDPOINT: localhost:9000
        OPENAI_API_KEY: sk-test-mock      # mocked, not real

    frontend-tests:
      runs-on: ubuntu-latest
      steps:
        - checkout
        - setup node 20
        - run: cd frontend && npm ci
        - run: cd frontend && npm run test -- --coverage
        - run: cd frontend && npm run build   # verify build succeeds

    e2e-tests:
      runs-on: ubuntu-latest
      needs: [unit-tests, integration-tests, frontend-tests]
      steps:
        - checkout
        - docker compose up -d
        - wait for health check
        - setup playwright
        - run: pytest tests/e2e/ -v --timeout=300
        - docker compose down
      artifacts:
        - playwright traces and screenshots on failure

    build-images:
      runs-on: ubuntu-latest
      needs: [e2e-tests]
      if: github.ref == 'refs/heads/main'
      steps:
        - build backend Docker image
        - build frontend Docker image
        - push to container registry (optional)

16.8 Test Configuration

# pytest.ini / pyproject.toml

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: unit tests (no external dependencies)",
    "integration: integration tests (require Docker services)",
    "e2e: end-to-end tests (require full stack)",
    "slow: tests that take > 30 seconds",
    "performance: performance/load tests",
]
filterwarnings = [
    "ignore::DeprecationWarning:sqlalchemy.*",
]
timeout = 30              # default timeout per test (seconds)
timeout_method = "signal"

# Run unit tests only:       pytest -m unit
# Run integration only:      pytest -m integration
# Run everything except e2e: pytest -m "not e2e"
# Run with coverage:         pytest -m "unit or integration" --cov=app

17. Observability & Monitoring
17.1 Structured Logging

logging:
  library: structlog (Python) with JSON output
  log_level: INFO (configurable via LOG_LEVEL env var)
  
  standard_fields:
    - timestamp (ISO 8601)
    - level (INFO, WARNING, ERROR, CRITICAL)
    - message
    - service (api | worker | pipeline)
    - request_id (UUID, propagated through request lifecycle)
    - company_id (when applicable)
    - document_id (when applicable)
    - duration_ms (for timed operations)
  
  log_events:
    # API
    - api.request.start:      {method, path, client_ip}
    - api.request.complete:   {method, path, status_code, duration_ms}
    - api.request.error:      {method, path, error, traceback}
    
    # Ingestion
    - ingestion.start:        {document_id, company_id, doc_type}
    - ingestion.parse.complete: {document_id, page_count, char_count, duration_ms}
    - ingestion.split.complete: {document_id, section_count, duration_ms}
    - ingestion.embed.complete: {document_id, chunk_count, vector_count, duration_ms}
    - ingestion.xbrl.complete:  {company_id, periods_extracted, duration_ms}
    - ingestion.complete:     {document_id, total_duration_ms}
    - ingestion.error:        {document_id, stage, error, traceback}
    
    # Chat
    - chat.request:           {company_id, session_id, message_length}
    - chat.retrieval:         {company_id, query_tokens, chunks_found, top_score, duration_ms}
    - chat.llm.start:         {model, prompt_tokens}
    - chat.llm.complete:      {model, prompt_tokens, completion_tokens, duration_ms, cost_usd}
    - chat.llm.error:         {model, error}
    
    # Analysis
    - analysis.run.start:     {company_id, profile_id, criteria_count}
    - analysis.run.complete:  {company_id, profile_id, score, duration_ms}
    - analysis.formula.error: {criterion_name, formula, error}
    
    # SEC EDGAR
    - sec.fetch.start:        {cik, filing_type, years_back}
    - sec.fetch.filing:       {cik, accession, filing_type, date}
    - sec.fetch.complete:     {cik, filings_downloaded, duration_ms}
    - sec.fetch.error:        {cik, error, status_code}
    - sec.rate_limit:         {wait_ms}
    
  sensitive_data_redaction:
    - Never log API keys (OPENAI_API_KEY, X-API-Key)
    - Never log full file contents
    - Truncate chat messages to first 100 chars in logs

17.2 Metrics

metrics:
  library: prometheus_client (Python)
  endpoint: /metrics (Prometheus scrape target)
  
  counters:
    - api_requests_total{method, path, status_code}
    - ingestion_documents_total{status}  # completed, failed
    - chat_messages_total{company_id}
    - analysis_runs_total{company_id, profile_id}
    - llm_api_calls_total{model, status}
    - sec_api_calls_total{endpoint, status}
    - embedding_api_calls_total{status}
  
  histograms:
    - api_request_duration_seconds{method, path}
    - ingestion_duration_seconds{stage}   # parse, split, embed, total
    - chat_retrieval_duration_seconds
    - chat_llm_duration_seconds{model}
    - analysis_duration_seconds
    - vector_search_duration_seconds
  
  gauges:
    - companies_total
    - documents_total{status}
    - vectors_total
    - celery_workers_active
    - celery_tasks_queued{queue}

17.3 Monitoring Dashboard (Optional)

monitoring_stack:
  profiles: ["monitoring"]  # optional docker-compose profile

  services:
    prometheus:
      image: prom/prometheus:latest
      config: scrape api /metrics every 15s
      port: 9090

    grafana:
      image: grafana/grafana:latest
      port: 3001
      dashboards:
        - API Performance (request rate, latency, errors)
        - Ingestion Pipeline (throughput, queue depth, failures)
        - LLM Usage (tokens, cost, latency)
        - Vector Store (search latency, collection sizes)
        - System Resources (CPU, memory per container)

    flower:
      # Already defined in docker-compose
      description: Celery task monitoring UI
      port: 5555

18. Error Handling & Resilience
18.1 Error Taxonomy

error_categories:

  validation_errors:
    http_status: 422
    examples:
      - Invalid ticker format
      - Missing required fields
      - Invalid fiscal quarter (must be 1-4)
      - Invalid formula expression
    behavior: return detailed error with field-level messages

  not_found_errors:
    http_status: 404
    examples:
      - Company not found
      - Document not found
      - Profile not found
      - Session not found
    behavior: return error with entity type and ID

  conflict_errors:
    http_status: 409
    examples:
      - Duplicate ticker
      - Duplicate document period
      - Duplicate profile name
    behavior: return error explaining what conflicts

  external_service_errors:
    http_status: 502
    examples:
      - OpenAI API failure
      - SEC EDGAR unreachable
      - Qdrant connection lost
    behavior: return error identifying the failing service, log full details

  rate_limit_errors:
    http_status: 429
    examples:
      - Too many chat requests
      - Too many API calls
      - SEC EDGAR rate limit
    behavior: return Retry-After header

  internal_errors:
    http_status: 500
    examples:
      - Unhandled exceptions
      - Database constraint violations not caught
    behavior: log full traceback, return generic error to client

18.2 Retry Policies

retry_policies:

  openai_api:
    max_retries: 3
    backoff: exponential (1s, 2s, 4s)
    retry_on:
      - 429 (rate limit)
      - 500 (server error)
      - 502 (bad gateway)
      - 503 (service unavailable)
      - ConnectionError
      - TimeoutError
    give_up_on:
      - 400 (bad request — our fault)
      - 401 (invalid key)

  sec_edgar_api:
    max_retries: 5
    backoff: exponential (2s, 4s, 8s, 16s, 32s)
    retry_on:
      - 429 (rate limit — respect Retry-After)
      - 500, 502, 503
      - ConnectionError
    rate_limit: max 10 requests/second (SEC policy)

  qdrant:
    max_retries: 3
    backoff: exponential (0.5s, 1s, 2s)
    retry_on:
      - ConnectionError
      - TimeoutError

  celery_tasks:
    max_retries: 3
    backoff: exponential (60s, 300s, 900s)
    retry_on:
      - any transient failure
    dead_letter: tasks that fail all retries are logged and marked as permanently failed

18.3 Circuit Breaker Pattern

circuit_breakers:

  openai:
    failure_threshold: 5          # consecutive failures to trip
    recovery_timeout: 60          # seconds before half-open
    half_open_max_calls: 2        # test calls in half-open state
    
    when_open:
      chat: return error "AI service temporarily unavailable"
      embeddings: queue ingestion tasks for later retry

  sec_edgar:
    failure_threshold: 10
    recovery_timeout: 300         # 5 minutes (SEC issues are often longer)
    when_open:
      fetch: return error "SEC EDGAR temporarily unavailable"
      note: does not affect already-uploaded document processing

  qdrant:
    failure_threshold: 3
    recovery_timeout: 30
    when_open:
      chat: return error "Search service temporarily unavailable"
      ingestion: pause embedding stage, resume when circuit closes

19. Configuration Management
19.1 Environment Variables

# ================================================================
# .env.example — Copy to .env and fill in values
# ================================================================

# ── Application ──────────────────────────────────────────────────
APP_NAME=company-analysis-platform
APP_VERSION=1.0.0
APP_ENV=development                     # development | staging | production
LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
API_KEY=your-secret-api-key-here        # authentication key for API access

# ── Database (PostgreSQL) ────────────────────────────────────────
DB_HOST=postgres
DB_PORT=5432
DB_NAME=company_analysis
DB_USER=analyst
DB_PASSWORD=change-this-in-production
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
DB_POOL_SIZE=10                         # connection pool size
DB_MAX_OVERFLOW=20                      # max overflow connections

# ── Vector Store (Qdrant) ────────────────────────────────────────
QDRANT_HOST=qdrant
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_URL=http://${QDRANT_HOST}:${QDRANT_HTTP_PORT}
QDRANT_API_KEY=                         # optional, for Qdrant Cloud
QDRANT_COLLECTION_PREFIX=company_       # prefix for per-company collections

# ── Object Storage (MinIO/S3) ────────────────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=change-this-in-production
MINIO_SECURE=false                      # true for HTTPS (production S3)
MINIO_BUCKET_FILINGS=filings
MINIO_BUCKET_EXPORTS=exports
# For AWS S3 instead of MinIO:
# S3_REGION=us-east-1
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...

# ── Redis ────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=20

# ── Celery Workers ───────────────────────────────────────────────
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
WORKER_CONCURRENCY=4                    # number of concurrent worker processes
CELERY_TASK_TIME_LIMIT=600              # hard time limit per task (seconds)
CELERY_TASK_SOFT_TIME_LIMIT=540         # soft limit (raises exception)

# ── OpenAI ───────────────────────────────────────────────────────
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_ORG_ID=                          # optional organization ID
LLM_MODEL=gpt-4o                        # chat model
LLM_FALLBACK_MODEL=gpt-4o-mini          # fallback if primary fails
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=120                         # seconds
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
EMBEDDING_BATCH_SIZE=64

# ── (Optional) Anthropic ────────────────────────────────────────
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# LLM_PROVIDER=anthropic                # switch provider
# LLM_MODEL=claude-sonnet-4-20250514

# ── RAG Configuration ───────────────────────────────────────────
RAG_TOP_K=15                            # chunks to retrieve
RAG_SCORE_THRESHOLD=0.65                # minimum similarity score
RAG_MAX_CONTEXT_TOKENS=12000            # context budget
RAG_MAX_HISTORY_TOKENS=4000             # history budget
RAG_MAX_HISTORY_EXCHANGES=10            # conversation turns to include

# ── Ingestion Configuration ──────────────────────────────────────
CHUNK_SIZE=768                          # target tokens per chunk
CHUNK_OVERLAP=128                       # overlap tokens
MAX_UPLOAD_SIZE_MB=50                   # max file upload size

# ── SEC EDGAR ────────────────────────────────────────────────────
SEC_EDGAR_USER_AGENT=CompanyAnalysis/1.0 (your-email@example.com)
SEC_EDGAR_RATE_LIMIT=10                 # max requests per second
SEC_EDGAR_BASE_URL=https://data.sec.gov

# ── API Server ───────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RATE_LIMIT_CRUD=100                 # requests per minute
API_RATE_LIMIT_CHAT=20                  # requests per minute

# ── Frontend ─────────────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Company Analysis Platform

# ── Ports (for docker-compose) ───────────────────────────────────
FRONTEND_PORT=3000
API_EXTERNAL_PORT=8000
DB_EXTERNAL_PORT=5432
QDRANT_EXTERNAL_HTTP_PORT=6333
QDRANT_EXTERNAL_GRPC_PORT=6334
REDIS_EXTERNAL_PORT=6379
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001
FLOWER_PORT=5555

19.2 Configuration Validation

# On application startup, validate ALL required configuration:

class AppConfig(BaseSettings):
    """Validated application configuration loaded from environment."""
    
    # All fields validated via Pydantic
    # Missing required fields → startup failure with clear error message
    # Invalid values → startup failure with validation details
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Startup validation:
    # 1. All required env vars present
    # 2. DATABASE_URL is valid connection string
    # 3. OPENAI_API_KEY starts with "sk-"
    # 4. SEC_EDGAR_USER_AGENT contains email address
    # 5. Numeric ranges valid (CHUNK_SIZE > 0, etc.)
    # 6. Connectivity check: ping DB, Redis, Qdrant, MinIO on startup

20. Implementation Phases & Milestones
Phase 1: Foundation (Core Infrastructure)

milestone: "System boots up and stores data"
duration_estimate: 3-5 days
deliverables:
  - Project scaffolding (monorepo structure)
  - Docker Compose with all services
  - FastAPI application skeleton with health check
  - PostgreSQL schema + Alembic migrations
  - Pydantic models for all entities
  - Company CRUD API (create, list, get, update, delete)
  - MinIO integration (bucket creation, file upload/download)
  - Configuration management (.env loading, validation)
  - Authentication middleware (API key)
  - Error handling middleware
  - Structured logging setup
  - Unit tests for company service
  - Integration tests for company API

verification:
  - docker compose up creates all services
  - GET /health returns healthy status
  - POST/GET/PUT/DELETE /companies works
  - Alembic migrations run cleanly

Phase 2: Ingestion Pipeline

milestone: "Documents can be uploaded, parsed, chunked, and embedded"
duration_estimate: 5-7 days
deliverables:
  - Document upload API (multipart file handling)
  - File storage in MinIO
  - PDF text extraction (PyMuPDF)
  - HTML text extraction (BeautifulSoup)
  - Text cleaning and normalization
  - Section splitter for 10-K and 10-Q
  - Text chunker with overlap
  - Qdrant collection management (create per company)
  - OpenAI embedding integration
  - Vector upsert to Qdrant
  - Celery worker setup with ingestion queue
  - Document status tracking (state machine)
  - Ingestion pipeline orchestrator (coordinates all stages)
  - Unit tests for parser, splitter, chunker
  - Integration tests for full pipeline

verification:
  - Upload PDF → status progresses to "ready"
  - Chunks visible in Qdrant dashboard
  - Section records in database match expected sections
  - Token counts are accurate
  - Duplicate upload returns 409

Phase 3: SEC EDGAR Integration

milestone: "Automatic filing fetch and financial data extraction"
duration_estimate: 3-5 days
deliverables:
  - SEC EDGAR client (ticker → CIK resolution)
  - Filing index fetcher (list available filings for company)
  - Filing download (fetch actual filing documents)
  - Rate limiting for SEC API calls
  - XBRL companyfacts API integration
  - XBRL tag → internal schema mapping (60+ tags)
  - Financial statements storage in PostgreSQL
  - Auto-fetch API endpoint
  - Celery queue for SEC fetch tasks
  - Financial data API endpoint
  - CSV export endpoint
  - Unit tests for XBRL mapper, SEC client
  - Integration tests for full fetch + extract flow

verification:
  - Auto-resolve CIK for AAPL → 0000320193
  - Fetch 10-K/10-Q filings for last 5 years
  - XBRL data extracted into financial_statements
  - Financial data API returns structured data
  - CSV export is valid and parseable

Phase 4: RAG Chat Agent

milestone: "Conversational AI agent answers questions about company filings"
duration_estimate: 5-7 days
deliverables:
  - Chat session management (create, list, get, delete)
  - Vector similarity search (query embedding + Qdrant search)
  - Metadata-filtered search (by year, doc type, section)
  - System prompt builder (company-specific)
  - Context assembly (retrieved chunks + history)
  - OpenAI chat completion with streaming
  - SSE endpoint for streaming responses
  - Source citation extraction and formatting
  - Conversation history management (token budget)
  - Message persistence
  - Session title auto-generation
  - Unit tests for prompt builder, retrieval logic
  - Integration tests for full chat flow (mocked LLM)

verification:
  - Chat creates session, returns streaming response
  - Response contains filing citations
  - Sources metadata returned via SSE
  - Follow-up questions use conversation context
  - Filtered search returns only matching documents
  - Session history persists and loads correctly

Phase 5: Financial Analysis Engine

milestone: "Automated financial scoring with user-defined criteria"
duration_estimate: 5-7 days
deliverables:
  - Formula registry (25+ built-in formulas)
  - Custom formula expression parser (lexer + parser + evaluator)
  - Analysis profile CRUD API
  - Analysis criteria management
  - Analysis execution engine:
    - Load financial data for company
    - Compute each formula across available years
    - Evaluate thresholds
    - Detect trends (linear regression)
    - Compute weighted scores
  - AI narrative summary generation (via LLM)
  - Analysis results persistence
  - Multi-company comparison endpoint
  - Unit tests for all formulas, parser, scorer, trend detection
  - Integration tests for full analysis flow

verification:
  - Create profile with 10 criteria → save succeeds
  - Run analysis → returns scored results with pass/fail per criterion
  - Custom formula "income_statement.revenue / balance_sheet.total_assets" computes correctly
  - Trend detection identifies obvious trends correctly
  - Multi-company comparison returns ranked results
  - AI summary references company and key findings

Phase 6: Frontend Application

milestone: "Full web UI for all platform features"
duration_estimate: 7-10 days
deliverables:
  - Next.js project setup with shadcn/ui
  - Layout: sidebar navigation + main content area
  - Dashboard page (company overview cards)
  - Company list page (with search, sort)
  - Company detail page with tabs:
    - Overview tab
    - Documents tab (upload, fetch, status tracking)
    - Financials tab (data table, charts)
    - Chat tab (streaming chat interface, sessions, sources)
    - Analysis tab (profile selector, run, score card, charts)
  - Analysis profiles management page
  - Multi-company comparison page
  - Settings page (view configuration)
  - Responsive design (desktop-first)
  - Loading states, error states, empty states
  - Frontend component tests (Vitest)

verification:
  - All pages render without errors
  - Chat streaming works in browser (tokens appear one by one)
  - Document upload via UI triggers processing
  - Analysis results display with colors and charts
  - Navigation between pages preserves state

Phase 7: Polish & Production Readiness

milestone: "System is production-ready for self-hosted deployment"
duration_estimate: 3-5 days
deliverables:
  - E2E tests for critical journeys
  - Performance testing and optimization
  - Production Docker images (multi-stage, non-root)
  - Production docker-compose.yml
  - Backup scripts
  - README.md with setup instructions
  - DEPLOYMENT.md with production deployment guide
  - Default analysis profile (Value Investor template)
  - Seed data script (creates sample profile)
  - Rate limiting implementation
  - Request validation hardening
  - Error message review (user-friendly)
  - Log output review (no sensitive data)
  - Dependency audit (security)
  - Documentation: API reference (auto-generated from FastAPI)

verification:
  - Fresh clone → docker compose up → fully functional system
  - All tests pass in CI
  - No security warnings in dependency audit
  - Backup and restore cycle works

21. Appendices
Appendix A: Built-in Financial Formulas

builtin_formulas:

  # ── PROFITABILITY ──────────────────────────────────────────────
  - name: gross_margin
    category: profitability
    description: "Gross profit as a percentage of revenue"
    formula: "income_statement.gross_profit / income_statement.revenue"
    required_fields: [gross_profit, revenue]
    unit: ratio
    typical_range: [0.20, 0.80]
    example_threshold: ">= 0.40 (40%)"

  - name: operating_margin
    category: profitability
    description: "Operating income as a percentage of revenue"
    formula: "income_statement.operating_income / income_statement.revenue"
    required_fields: [operating_income, revenue]
    unit: ratio
    typical_range: [0.05, 0.40]

  - name: net_margin
    category: profitability
    description: "Net income as a percentage of revenue"
    formula: "income_statement.net_income / income_statement.revenue"
    required_fields: [net_income, revenue]
    unit: ratio
    typical_range: [0.03, 0.30]

  - name: roe
    category: profitability
    description: "Return on equity — net income divided by total shareholders' equity"
    formula: "income_statement.net_income / balance_sheet.total_equity"
    required_fields: [net_income, total_equity]
    unit: ratio
    typical_range: [0.08, 0.40]
    note: "Negative equity makes ROE misleading"

  - name: roa
    category: profitability
    description: "Return on assets — net income divided by total assets"
    formula: "income_statement.net_income / balance_sheet.total_assets"
    required_fields: [net_income, total_assets]
    unit: ratio
    typical_range: [0.03, 0.20]

  - name: roic
    category: profitability
    description: "Return on invested capital — NOPAT divided by invested capital"
    formula: >
      (income_statement.operating_income * (1 - 0.21)) /
      (balance_sheet.total_assets - balance_sheet.total_current_liabilities - balance_sheet.cash_and_equivalents)
    required_fields: [operating_income, total_assets, total_current_liabilities, cash_and_equivalents]
    unit: ratio
    typical_range: [0.08, 0.30]
    note: "Uses statutory 21% tax rate as approximation"

  # ── GROWTH ─────────────────────────────────────────────────────
  - name: revenue_growth
    category: growth
    description: "Year-over-year revenue growth rate"
    formula: "(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)"
    required_fields: [revenue]
    requires_prior_period: true
    unit: ratio
    typical_range: [-0.10, 0.50]

  - name: earnings_growth
    category: growth
    description: "Year-over-year net income growth rate"
    formula: "(income_statement.net_income - prev(income_statement.net_income)) / abs(prev(income_statement.net_income))"
    required_fields: [net_income]
    requires_prior_period: true
    unit: ratio

  - name: operating_income_growth
    category: growth
    description: "Year-over-year operating income growth rate"
    formula: "(income_statement.operating_income - prev(income_statement.operating_income)) / abs(prev(income_statement.operating_income))"
    required_fields: [operating_income]
    requires_prior_period: true
    unit: ratio

  - name: fcf_growth
    category: growth
    description: "Year-over-year free cash flow growth rate"
    formula: "(cash_flow.free_cash_flow - prev(cash_flow.free_cash_flow)) / abs(prev(cash_flow.free_cash_flow))"
    required_fields: [free_cash_flow]
    requires_prior_period: true
    unit: ratio

  # ── LIQUIDITY ──────────────────────────────────────────────────
  - name: current_ratio
    category: liquidity
    description: "Current assets divided by current liabilities"
    formula: "balance_sheet.total_current_assets / balance_sheet.total_current_liabilities"
    required_fields: [total_current_assets, total_current_liabilities]
    unit: ratio
    typical_range: [1.0, 3.0]

  - name: quick_ratio
    category: liquidity
    description: "Liquid assets (current assets minus inventory) divided by current liabilities"
    formula: "(balance_sheet.total_current_assets - balance_sheet.inventory) / balance_sheet.total_current_liabilities"
    required_fields: [total_current_assets, inventory, total_current_liabilities]
    unit: ratio

  - name: cash_ratio
    category: liquidity
    description: "Cash and equivalents divided by current liabilities"
    formula: "balance_sheet.cash_and_equivalents / balance_sheet.total_current_liabilities"
    required_fields: [cash_and_equivalents, total_current_liabilities]
    unit: ratio

  # ── SOLVENCY / LEVERAGE ────────────────────────────────────────
  - name: debt_to_equity
    category: solvency
    description: "Total long-term debt divided by total equity"
    formula: "balance_sheet.long_term_debt / balance_sheet.total_equity"
    required_fields: [long_term_debt, total_equity]
    unit: ratio
    typical_range: [0, 2.0]

  - name: total_debt_to_equity
    category: solvency
    description: "Total debt (short + long term) divided by total equity"
    formula: "(balance_sheet.short_term_debt + balance_sheet.long_term_debt) / balance_sheet.total_equity"
    required_fields: [short_term_debt, long_term_debt, total_equity]
    unit: ratio

  - name: debt_to_assets
    category: solvency
    description: "Total liabilities divided by total assets"
    formula: "balance_sheet.total_liabilities / balance_sheet.total_assets"
    required_fields: [total_liabilities, total_assets]
    unit: ratio
    typical_range: [0.20, 0.70]

  - name: interest_coverage
    category: solvency
    description: "Operating income divided by interest expense"
    formula: "income_statement.operating_income / income_statement.interest_expense"
    required_fields: [operating_income, interest_expense]
    unit: times
    typical_range: [3.0, 50.0]
    note: "Higher is better. < 1.5 is concerning."

  # ── EFFICIENCY ─────────────────────────────────────────────────
  - name: asset_turnover
    category: efficiency
    description: "Revenue divided by total assets"
    formula: "income_statement.revenue / balance_sheet.total_assets"
    required_fields: [revenue, total_assets]
    unit: times

  - name: inventory_turnover
    category: efficiency
    description: "Cost of revenue divided by inventory"
    formula: "income_statement.cost_of_revenue / balance_sheet.inventory"
    required_fields: [cost_of_revenue, inventory]
    unit: times
    note: "Not applicable for service companies (inventory may be 0)"

  - name: receivables_turnover
    category: efficiency
    description: "Revenue divided by accounts receivable"
    formula: "income_statement.revenue / balance_sheet.accounts_receivable"
    required_fields: [revenue, accounts_receivable]
    unit: times

  # ── CASH FLOW QUALITY ──────────────────────────────────────────
  - name: fcf_margin
    category: quality
    description: "Free cash flow as a percentage of revenue"
    formula: "cash_flow.free_cash_flow / income_statement.revenue"
    required_fields: [free_cash_flow, revenue]
    unit: ratio
    typical_range: [0.05, 0.35]

  - name: operating_cash_flow_ratio
    category: quality
    description: "Operating cash flow divided by net income (earnings quality indicator)"
    formula: "cash_flow.operating_cash_flow / income_statement.net_income"
    required_fields: [operating_cash_flow, net_income]
    unit: ratio
    note: "> 1.0 indicates strong cash conversion"

  - name: capex_to_revenue
    category: quality
    description: "Capital expenditure intensity (capex as % of revenue)"
    formula: "abs(cash_flow.capital_expenditure) / income_statement.revenue"
    required_fields: [capital_expenditure, revenue]
    unit: ratio
    note: "Lower is generally better for capital-light businesses"

  - name: fcf_to_net_income
    category: quality
    description: "Free cash flow conversion ratio"
    formula: "cash_flow.free_cash_flow / income_statement.net_income"
    required_fields: [free_cash_flow, net_income]
    unit: ratio
    note: "> 1.0 indicates FCF exceeds reported earnings"

  # ── DIVIDEND ───────────────────────────────────────────────────
  - name: dividend_payout_ratio
    category: dividend
    description: "Dividends paid as percentage of net income"
    formula: "abs(cash_flow.dividends_paid) / income_statement.net_income"
    required_fields: [dividends_paid, net_income]
    unit: ratio
    typical_range: [0.20, 0.60]

  - name: buyback_yield
    category: dividend
    description: "Share repurchases as percentage of market cap (approximated)"
    formula: "abs(cash_flow.share_buybacks) / (income_statement.eps_diluted * income_statement.shares_outstanding_diluted)"
    required_fields: [share_buybacks, eps_diluted, shares_outstanding_diluted]
    unit: ratio
    note: "Approximation using earnings-based market cap proxy. Not precise."

  # ── COMPOSITE / SPECIAL ────────────────────────────────────────
  - name: sbc_to_revenue
    category: quality
    description: "Stock-based compensation as percentage of revenue"
    formula: "cash_flow.stock_based_compensation / income_statement.revenue"
    required_fields: [stock_based_compensation, revenue]
    unit: ratio
    note: "High SBC dilutes shareholders. > 10% is a red flag for many investors."

  - name: rd_to_revenue
    category: efficiency
    description: "R&D spending as percentage of revenue"
    formula: "income_statement.research_and_development / income_statement.revenue"
    required_fields: [research_and_development, revenue]
    unit: ratio
    note: "Varies significantly by industry. Tech typically 10-25%."

Appendix B: XBRL Tag Mapping

xbrl_tag_mapping:
  # Maps US-GAAP XBRL taxonomy tags to internal financial data fields
  # Some concepts have multiple possible tags (companies may use different ones)
  # Priority: first matching tag wins

  income_statement:
    revenue:
      tags:
        - "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        - "us-gaap:Revenues"
        - "us-gaap:SalesRevenueNet"
        - "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"
      period_type: duration  # 12 months for annual, 3 months for quarterly

    cost_of_revenue:
      tags:
        - "us-gaap:CostOfGoodsAndServicesSold"
        - "us-gaap:CostOfRevenue"
        - "us-gaap:CostOfGoodsSold"

    gross_profit:
      tags:
        - "us-gaap:GrossProfit"
      fallback_formula: "revenue - cost_of_revenue"

    research_and_development:
      tags:
        - "us-gaap:ResearchAndDevelopmentExpense"
        - "us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"

    selling_general_admin:
      tags:
        - "us-gaap:SellingGeneralAndAdministrativeExpense"
        - "us-gaap:GeneralAndAdministrativeExpense"

    operating_income:
      tags:
        - "us-gaap:OperatingIncomeLoss"

    interest_expense:
      tags:
        - "us-gaap:InterestExpense"
        - "us-gaap:InterestExpenseDebt"

    interest_income:
      tags:
        - "us-gaap:InvestmentIncomeInterest"
        - "us-gaap:InterestIncomeExpenseNet"

    income_before_tax:
      tags:
        - "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
        - "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"

    income_tax_expense:
      tags:
        - "us-gaap:IncomeTaxExpenseBenefit"

    net_income:
      tags:
        - "us-gaap:NetIncomeLoss"
        - "us-gaap:ProfitLoss"

    eps_basic:
      tags:
        - "us-gaap:EarningsPerShareBasic"
      per_share: true

    eps_diluted:
      tags:
        - "us-gaap:EarningsPerShareDiluted"
      per_share: true

    shares_outstanding_basic:
      tags:
        - "us-gaap:WeightedAverageNumberOfShareOutstandingBasicAndDiluted"
        - "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic"
      period_type: duration

    shares_outstanding_diluted:
      tags:
        - "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
      period_type: duration

    depreciation_amortization:
      tags:
        - "us-gaap:DepreciationDepletionAndAmortization"
        - "us-gaap:DepreciationAmortizationAndAccretionNet"

  balance_sheet:
    cash_and_equivalents:
      tags:
        - "us-gaap:CashAndCashEquivalentsAtCarryingValue"
        - "us-gaap:Cash"
      period_type: instant

    short_term_investments:
      tags:
        - "us-gaap:ShortTermInvestments"
        - "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent"
      period_type: instant

    accounts_receivable:
      tags:
        - "us-gaap:AccountsReceivableNetCurrent"
        - "us-gaap:ReceivablesNetCurrent"
      period_type: instant

    inventory:
      tags:
        - "us-gaap:InventoryNet"
        - "us-gaap:InventoryFinishedGoodsNetOfReserves"
      period_type: instant

    total_current_assets:
      tags:
        - "us-gaap:AssetsCurrent"
      period_type: instant

    property_plant_equipment:
      tags:
        - "us-gaap:PropertyPlantAndEquipmentNet"
      period_type: instant

    goodwill:
      tags:
        - "us-gaap:Goodwill"
      period_type: instant

    intangible_assets:
      tags:
        - "us-gaap:IntangibleAssetsNetExcludingGoodwill"
        - "us-gaap:FiniteLivedIntangibleAssetsNet"
      period_type: instant

    total_assets:
      tags:
        - "us-gaap:Assets"
      period_type: instant

    accounts_payable:
      tags:
        - "us-gaap:AccountsPayableCurrent"
      period_type: instant

    short_term_debt:
      tags:
        - "us-gaap:ShortTermBorrowings"
        - "us-gaap:LongTermDebtCurrent"
        - "us-gaap:DebtCurrent"
      period_type: instant

    total_current_liabilities:
      tags:
        - "us-gaap:LiabilitiesCurrent"
      period_type: instant

    long_term_debt:
      tags:
        - "us-gaap:LongTermDebtNoncurrent"
        - "us-gaap:LongTermDebt"
      period_type: instant

    total_liabilities:
      tags:
        - "us-gaap:Liabilities"
      period_type: instant

    total_equity:
      tags:
        - "us-gaap:StockholdersEquity"
        - "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
      period_type: instant

    retained_earnings:
      tags:
        - "us-gaap:RetainedEarningsAccumulatedDeficit"
      period_type: instant

    common_stock:
      tags:
        - "us-gaap:CommonStocksIncludingAdditionalPaidInCapital"
        - "us-gaap:CommonStockValue"
      period_type: instant

  cash_flow:
    operating_cash_flow:
      tags:
        - "us-gaap:NetCashProvidedByUsedInOperatingActivities"
      period_type: duration

    capital_expenditure:
      tags:
        - "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
        - "us-gaap:PaymentsToAcquireProductiveAssets"
      period_type: duration
      negate: true  # typically reported as positive, store as negative

    investing_cash_flow:
      tags:
        - "us-gaap:NetCashProvidedByUsedInInvestingActivities"
      period_type: duration

    financing_cash_flow:
      tags:
        - "us-gaap:NetCashProvidedByUsedInFinancingActivities"
      period_type: duration

    dividends_paid:
      tags:
        - "us-gaap:PaymentsOfDividendsCommonStock"
        - "us-gaap:PaymentsOfDividends"
      period_type: duration
      negate: true

    share_buybacks:
      tags:
        - "us-gaap:PaymentsForRepurchaseOfCommonStock"
        - "us-gaap:PaymentsForRepurchaseOfEquity"
      period_type: duration
      negate: true

    debt_issued:
      tags:
        - "us-gaap:ProceedsFromIssuanceOfLongTermDebt"
        - "us-gaap:ProceedsFromDebtNetOfIssuanceCosts"
      period_type: duration

    debt_repaid:
      tags:
        - "us-gaap:RepaymentsOfLongTermDebt"
        - "us-gaap:RepaymentsOfDebt"
      period_type: duration
      negate: true

    stock_based_compensation:
      tags:
        - "us-gaap:ShareBasedCompensation"
        - "us-gaap:AllocatedShareBasedCompensationExpense"
      period_type: duration

    free_cash_flow:
      fallback_formula: "operating_cash_flow + capital_expenditure"
      note: "Not a standard XBRL tag; computed from CFO + CapEx"

  period_selection_rules:
    annual:
      # Select facts where the duration is approximately 12 months (365 ± 30 days)
      # For instant items, select the end-of-fiscal-year date
      duration_days_min: 335
      duration_days_max: 395
    quarterly:
      # Select facts where the duration is approximately 3 months (90 ± 15 days)
      duration_days_min: 75
      duration_days_max: 105
    disambiguation:
      # When multiple values exist for the same period:
      # 1. Prefer values from the company's own filing (not amendments)
      # 2. Prefer values with form type "10-K" over "10-K/A"
      # 3. Prefer the most recently filed value
      priority:
        - same_fiscal_period_latest_filing
        - exclude_amendments_if_original_exists

Appendix C: SEC Filing Section Reference

# 10-K Standard Sections (as of 2024)

ten_k_sections:
  part_i:
    item_1:
      title: "Business"
      key: "item_1"
      importance: high
      content: >
        Company overview, products/services, customers, competition,
        regulation, employees, organizational structure
    item_1a:
      title: "Risk Factors"
      key: "item_1a"
      importance: critical
      content: >
        Material risks to the business, market, financial condition.
        Often 20-50 pages. Key for qualitative analysis.
    item_1b:
      title: "Unresolved Staff Comments"
      key: "item_1b"
      importance: low
      content: >
        Outstanding SEC staff review comments
    item_1c:
      title: "Cybersecurity"
      key: "item_1c"
      importance: medium
      content: >
        Cybersecurity risk management, strategy, governance.
        New requirement starting 2023.
    item_2:
      title: "Properties"
      key: "item_2"
      importance: low
      content: >
        Description of material physical properties
    item_3:
      title: "Legal Proceedings"
      key: "item_3"
      importance: medium
      content: >
        Material litigation, regulatory actions
    item_4:
      title: "Mine Safety Disclosures"
      key: "item_4"
      importance: low
      content: >
        Only applicable to mining companies

  part_ii:
    item_5:
      title: "Market for Registrant's Common Equity"
      key: "item_5"
      importance: medium
      content: >
        Stock exchange, dividends, share repurchases,
        stock performance comparison
    item_6:
      title: "Reserved"
      key: "item_6"
      importance: none
      content: >
        Previously "Selected Financial Data" — eliminated by SEC in 2021
    item_7:
      title: "Management's Discussion and Analysis (MD&A)"
      key: "item_7"
      importance: critical
      content: >
        Management's perspective on financial results, liquidity,
        capital resources, outlook. Often 30-60 pages.
        THE most important section for qualitative analysis.
    item_7a:
      title: "Quantitative and Qualitative Disclosures About Market Risk"
      key: "item_7a"
      importance: medium
      content: >
        Interest rate risk, foreign currency risk, commodity risk
    item_8:
      title: "Financial Statements and Supplementary Data"
      key: "item_8"
      importance: critical
      content: >
        Full financial statements (IS, BS, CF, equity statement)
        plus notes. Typically 40-80 pages.
        Primary source for quantitative analysis.
    item_9:
      title: "Changes in and Disagreements with Accountants"
      key: "item_9"
      importance: low
    item_9a:
      title: "Controls and Procedures"
      key: "item_9a"
      importance: medium
      content: >
        Internal controls assessment, auditor opinion on controls

  part_iii:
    item_10:
      title: "Directors, Executive Officers and Corporate Governance"
      key: "item_10"
      importance: low
    item_11:
      title: "Executive Compensation"
      key: "item_11"
      importance: medium
    item_12:
      title: "Security Ownership of Certain Beneficial Owners"
      key: "item_12"
      importance: low
    item_13:
      title: "Certain Relationships and Related Transactions"
      key: "item_13"
      importance: low
    item_14:
      title: "Principal Accountant Fees and Services"
      key: "item_14"
      importance: low

# 10-Q Standard Sections

ten_q_sections:
  part_i:
    item_1:
      title: "Financial Statements"
      key: "item_1"
      importance: critical
    item_2:
      title: "Management's Discussion and Analysis (MD&A)"
      key: "item_2"
      importance: critical
    item_3:
      title: "Quantitative and Qualitative Disclosures About Market Risk"
      key: "item_3"
      importance: medium
    item_4:
      title: "Controls and Procedures"
      key: "item_4"
      importance: medium

  part_ii:
    item_1:
      title: "Legal Proceedings"
      key: "part2_item_1"
      importance: medium
    item_1a:
      title: "Risk Factors"
      key: "part2_item_1a"
      importance: high
      content: "Updates to risk factors since last 10-K"
    item_2:
      title: "Unregistered Sales of Equity Securities"
      key: "part2_item_2"
      importance: low
    item_6:
      title: "Exhibits"
      key: "part2_item_6"
      importance: low

Appendix D: Default Analysis Profile Template

# This profile is seeded into the system on first startup
# Users can modify it or create their own

default_profile:
  name: "Quality Value Investor"
  description: >
    A balanced analysis profile for quality-focused value investors.
    Evaluates profitability, capital efficiency, financial health,
    growth, and cash flow quality. Suitable for established companies
    with 5+ years of financial history.
  is_default: true
  
  criteria:
    # ── PROFITABILITY (weight emphasis) ──────────
    - name: "Gross Margin > 40%"
      category: profitability
      description: "High gross margin indicates pricing power and competitive advantage"
      formula: gross_margin
      comparison: ">="
      threshold_value: 0.40
      weight: 2.0
      lookback_years: 5
      sort_order: 1

    - name: "Operating Margin > 15%"
      category: profitability
      description: "Strong operating efficiency"
      formula: operating_margin
      comparison: ">="
      threshold_value: 0.15
      weight: 2.0
      lookback_years: 5
      sort_order: 2

    - name: "Net Margin > 10%"
      category: profitability
      description: "Healthy bottom-line profitability"
      formula: net_margin
      comparison: ">="
      threshold_value: 0.10
      weight: 1.5
      lookback_years: 5
      sort_order: 3

    - name: "ROE > 15%"
      category: profitability
      description: "Strong return on shareholder equity"
      formula: roe
      comparison: ">="
      threshold_value: 0.15
      weight: 2.5
      lookback_years: 5
      sort_order: 4

    - name: "ROIC > 12%"
      category: profitability
      description: "Creating value above cost of capital"
      formula: roic
      comparison: ">="
      threshold_value: 0.12
      weight: 3.0
      lookback_years: 5
      sort_order: 5

    # ── GROWTH ───────────────────────────────────
    - name: "Revenue Growth > 5%"
      category: growth
      description: "Moderate top-line growth"
      formula: revenue_growth
      comparison: ">="
      threshold_value: 0.05
      weight: 1.5
      lookback_years: 5
      sort_order: 6

    - name: "Earnings Growth Positive"
      category: growth
      description: "Growing earnings year over year"
      formula: earnings_growth
      comparison: ">"
      threshold_value: 0.0
      weight: 1.0
      lookback_years: 5
      sort_order: 7

    - name: "Revenue Trend Improving"
      category: growth
      description: "Revenue shows upward trend over multiple years"
      formula: revenue_growth
      comparison: "trend_up"
      weight: 1.0
      lookback_years: 5
      sort_order: 8

    # ── SOLVENCY / LEVERAGE ──────────────────────
    - name: "Debt-to-Equity < 1.0"
      category: solvency
      description: "Conservative leverage — debt less than equity"
      formula: debt_to_equity
      comparison: "<="
      threshold_value: 1.0
      weight: 2.0
      lookback_years: 5
      sort_order: 9

    - name: "Interest Coverage > 5x"
      category: solvency
      description: "Comfortable ability to service debt obligations"
      formula: interest_coverage
      comparison: ">="
      threshold_value: 5.0
      weight: 1.5
      lookback_years: 5
      sort_order: 10

    # ── LIQUIDITY ────────────────────────────────
    - name: "Current Ratio > 1.2"
      category: liquidity
      description: "Adequate short-term liquidity"
      formula: current_ratio
      comparison: ">="
      threshold_value: 1.2
      weight: 1.0
      lookback_years: 3
      sort_order: 11

    # ── CASH FLOW QUALITY ────────────────────────
    - name: "FCF Margin > 10%"
      category: quality
      description: "Strong free cash flow generation relative to revenue"
      formula: fcf_margin
      comparison: ">="
      threshold_value: 0.10
      weight: 2.5
      lookback_years: 5
      sort_order: 12

    - name: "OCF > Net Income"
      category: quality
      description: "Cash earnings exceed accrual earnings (quality indicator)"
      formula: operating_cash_flow_ratio
      comparison: ">="
      threshold_value: 1.0
      weight: 2.0
      lookback_years: 5
      sort_order: 13

    - name: "FCF Conversion > 80%"
      category: quality
      description: "FCF is at least 80% of net income"
      formula: fcf_to_net_income
      comparison: ">="
      threshold_value: 0.80
      weight: 1.5
      lookback_years: 5
      sort_order: 14

    - name: "SBC < 5% of Revenue"
      category: quality
      description: "Stock-based compensation is not excessive"
      formula: sbc_to_revenue
      comparison: "<="
      threshold_value: 0.05
      weight: 1.0
      lookback_years: 3
      sort_order: 15

Appendix E: Project Directory Structure

company-analysis-platform/
├── README.md
├── DEPLOYMENT.md
├── LICENSE
├── docker-compose.yml
├── docker-compose.override.yml      # dev overrides (volume mounts)
├── .env.example
├── .gitignore
├── Makefile                          # common commands
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt          # test + dev dependencies
│   ├── pyproject.toml                # ruff, mypy, pytest config
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── ...
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # Pydantic Settings
│   │   ├── dependencies.py           # FastAPI dependency injection
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # top-level router (includes all sub-routers)
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py           # API key authentication
│   │   │   │   ├── error_handler.py  # global error handling
│   │   │   │   ├── logging.py        # request logging
│   │   │   │   └── rate_limit.py     # rate limiting
│   │   │   ├── companies.py          # company endpoints
│   │   │   ├── documents.py          # document endpoints
│   │   │   ├── chat.py               # chat endpoints (SSE)
│   │   │   ├── analysis.py           # analysis endpoints
│   │   │   ├── financials.py         # financial data endpoints
│   │   │   ├── health.py             # health check endpoint
│   │   │   └── tasks.py              # async task status endpoint
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # declarative base, mixins
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
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── company.py            # CompanyCreate, CompanyRead, CompanyList
│   │   │   ├── document.py           # DocumentUpload, DocumentRead, DocumentStatus
│   │   │   ├── chat.py               # ChatRequest, ChatMessage, SessionRead
│   │   │   ├── analysis.py           # ProfileCreate, CriterionDef, AnalysisResult
│   │   │   ├── financial.py          # FinancialPeriod, FinancialExport
│   │   │   └── common.py             # PaginatedResponse, ErrorResponse
│   │   │
│   │   ├── services/                 # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── company_service.py
│   │   │   ├── document_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── analysis_service.py
│   │   │   └── financial_service.py
│   │   │
│   │   ├── ingestion/                # Document processing pipeline
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py           # orchestrator
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── html_parser.py
│   │   │   │   └── text_cleaner.py
│   │   │   ├── section_splitter.py
│   │   │   ├── chunker.py
│   │   │   └── embedding_service.py
│   │   │
│   │   ├── analysis/                 # Financial analysis engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # main analysis orchestrator
│   │   │   ├── formula_registry.py   # built-in formula definitions
│   │   │   ├── formula_parser.py     # custom expression parser
│   │   │   ├── threshold_evaluator.py
│   │   │   ├── trend_detector.py
│   │   │   └── scorer.py
│   │   │
│   │   ├── rag/                      # RAG chat agent
│   │   │   ├── __init__.py
│   │   │   ├── agent.py              # CompanyChatAgent
│   │   │   ├── retriever.py          # vector search + filtering
│   │   │   ├── prompt_builder.py     # system prompt + context assembly
│   │   │   └── query_expander.py     # optional query expansion
│   │   │
│   │   ├── clients/                  # External service clients
│   │   │   ├── __init__.py
│   │   │   ├── openai_client.py      # embeddings + chat completions
│   │   │   ├── sec_edgar_client.py   # EDGAR API interactions
│   │   │   ├── qdrant_client.py      # vector DB operations
│   │   │   └── storage_client.py     # MinIO/S3 operations
│   │   │
│   │   ├── db/                       # Database utilities
│   │   │   ├── __init__.py
│   │   │   ├── session.py            # async session factory
│   │   │   └── repositories/         # data access layer
│   │   │       ├── __init__.py
│   │   │       ├── company_repo.py
│   │   │       ├── document_repo.py
│   │   │       ├── financial_repo.py
│   │   │       ├── profile_repo.py
│   │   │       ├── result_repo.py
│   │   │       └── chat_repo.py
│   │   │
│   │   ├── worker/                   # Celery worker
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py         # Celery configuration
│   │   │   ├── tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ingestion_tasks.py
│   │   │   │   ├── analysis_tasks.py
│   │   │   │   └── sec_fetch_tasks.py
│   │   │   └── callbacks.py          # task success/failure handlers
│   │   │
│   │   └── xbrl/                     # XBRL processing
│   │       ├── __init__.py
│   │       ├── mapper.py             # XBRL tag → internal schema mapping
│   │       ├── tag_registry.py       # known XBRL tags and alternatives
│   │       └── period_selector.py    # select correct period from facts
│   │
│   └── tests/
│       ├── conftest.py               # shared fixtures
│       ├── factories.py              # test data factories
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
│       │   ├── conftest.py           # testcontainers setup
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
│   │   ├── app/                      # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # → /dashboard
│   │   │   ├── companies/
│   │   │   │   ├── page.tsx          # company list
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx      # company detail (tabs)
│   │   │   │       └── layout.tsx
│   │   │   ├── analysis/
│   │   │   │   ├── profiles/
│   │   │   │   │   ├── page.tsx
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx  # profile editor
│   │   │   │   └── compare/
│   │   │   │       └── page.tsx
│   │   │   └── settings/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui components
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
│   │   │   │   └── ... (other shadcn components)
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
│   │   │   ├── use-companies.ts      # React Query hooks
│   │   │   ├── use-documents.ts
│   │   │   ├── use-chat.ts
│   │   │   ├── use-analysis.ts
│   │   │   ├── use-financials.ts
│   │   │   ├── use-sse.ts            # SSE stream hook
│   │   │   └── use-debounce.ts
│   │   │
│   │   ├── lib/
│   │   │   ├── api-client.ts         # configured HTTP client
│   │   │   ├── sse-client.ts         # SSE stream parser
│   │   │   ├── formatters.ts         # number/date formatting
│   │   │   ├── constants.ts
│   │   │   ├── types.ts              # TypeScript types matching API schemas
│   │   │   └── utils.ts              # cn() helper, etc.
│   │   │
│   │   └── providers/
│   │       ├── query-provider.tsx    # React Query provider
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
    ├── setup.sh                      # first-time setup (create .env, init DB)
    ├── seed.sh                       # seed default analysis profile
    ├── backup.sh                     # run backups
    └── reset.sh                      # wipe all data (development)


Appendix F: Makefile Commands

# Makefile — Common commands for development and operations

.PHONY: help setup up down logs test lint migrate seed backup

help:                               ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk \
		'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup & Infrastructure ──────────────────────────────────
setup:                              ## First-time setup (copy .env, build images)
	cp -n .env.example .env || true
	docker compose build
	docker compose run --rm api alembic upgrade head
	docker compose run --rm api python -m app.scripts.seed_defaults

up:                                 ## Start all services
	docker compose up -d

up-full:                            ## Start all services including monitoring
	docker compose --profile monitoring up -d

down:                               ## Stop all services
	docker compose down

restart:                            ## Restart all services
	docker compose restart

logs:                               ## Tail logs for all services
	docker compose logs -f --tail=100

logs-api:                           ## Tail API logs
	docker compose logs -f --tail=100 api

logs-worker:                        ## Tail worker logs
	docker compose logs -f --tail=100 worker

# ── Database ────────────────────────────────────────────────
migrate:                            ## Run database migrations
	docker compose run --rm api alembic upgrade head

migrate-new:                        ## Create new migration (pass MESSAGE="description")
	docker compose run --rm api alembic revision --autogenerate -m "$(MESSAGE)"

migrate-rollback:                   ## Rollback last migration
	docker compose run --rm api alembic downgrade -1

db-shell:                           ## Open PostgreSQL shell
	docker compose exec postgres psql -U analyst -d company_analysis

# ── Testing ─────────────────────────────────────────────────
test:                               ## Run all tests (unit + integration)
	docker compose run --rm api pytest tests/unit tests/integration -v

test-unit:                          ## Run unit tests only
	docker compose run --rm api pytest tests/unit -v

test-integration:                   ## Run integration tests only
	docker compose run --rm api pytest tests/integration -v

test-e2e:                           ## Run end-to-end tests
	docker compose run --rm api pytest tests/e2e -v --timeout=300

test-coverage:                      ## Run tests with coverage report
	docker compose run --rm api pytest tests/unit tests/integration \
		--cov=app --cov-report=html --cov-report=term --cov-fail-under=85

test-frontend:                      ## Run frontend tests
	docker compose run --rm frontend npm test

# ── Code Quality ────────────────────────────────────────────
lint:                               ## Run linters
	docker compose run --rm api ruff check app/
	docker compose run --rm api ruff format --check app/
	docker compose run --rm api mypy app/ --strict

lint-fix:                           ## Auto-fix linting issues
	docker compose run --rm api ruff check --fix app/
	docker compose run --rm api ruff format app/

# ── Data & Operations ──────────────────────────────────────
seed:                               ## Seed default analysis profile
	docker compose run --rm api python -m app.scripts.seed_defaults

backup:                             ## Run backup of all data stores
	./scripts/backup.sh

reset:                              ## ⚠️  Wipe ALL data (development only)
	docker compose down -v
	docker compose up -d
	sleep 5
	$(MAKE) migrate
	$(MAKE) seed

# ── Debugging ──────────────────────────────────────────────
shell:                              ## Open Python shell in API container
	docker compose run --rm api python

flower:                             ## Open Celery Flower (task monitor)
	@echo "Flower UI: http://localhost:5555"
	docker compose --profile monitoring up -d worker-monitor

qdrant-dashboard:                   ## Show Qdrant dashboard URL
	@echo "Qdrant Dashboard: http://localhost:6333/dashboard"

minio-console:                      ## Show MinIO console URL
	@echo "MinIO Console: http://localhost:9001"

End of Specification

This document contains all information necessary to implement the Public Company Analysis Platform. An implementor (human or AI) should be able to build the complete system by following this specification without requiring additional clarification.

Key implementation order: Follow the phases in Section 20. Each phase builds on the previous one and has clear verification criteria.

When in doubt, the implementor should:

Prefer simplicity over cleverness
Prefer explicit over implicit
Write tests before or alongside implementation
Use the exact data models, API signatures, and configurations specified
Log decisions that deviate from the spec

