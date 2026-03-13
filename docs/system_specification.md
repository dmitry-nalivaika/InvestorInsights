---
document_type: system_specification
version: "2.0.0"
status: draft
created: 2025-01-XX
target_audience: LLM-as-implementor (Claude Opus), human reviewers
purpose: >
  Complete specification for an AI-powered public company analysis platform.
  This document should contain ALL information necessary for an implementor
  to build the system end-to-end without further clarification.
---

# InvestorInsights — System Specification

## Table of Contents

1.  [Executive Summary](#1-executive-summary)
    - [1.1 Problem Statement](#11-problem-statement)
    - [1.2 Solution](#12-solution)
    - [1.3 Key Design Principles](#13-key-design-principles)
2.  [Glossary & Definitions](#2-glossary--definitions)
3.  [User Personas & Stories](#3-user-personas--stories)
    - [3.1 Primary Persona](#31-primary-persona-independent-equity-analyst)
    - [3.2 User Stories](#32-user-stories)
4.  [Functional Requirements](#4-functional-requirements)
    - [4.1 Company Management (FR-1xx)](#41-company-management-fr-1xx)
    - [4.2 Document Management (FR-2xx)](#42-document-management-fr-2xx)
    - [4.3 Ingestion Pipeline (FR-3xx)](#43-ingestion-pipeline-fr-3xx)
    - [4.4 Chat Agent (FR-4xx)](#44-chat-agent-fr-4xx)
    - [4.5 Financial Analysis Engine (FR-5xx)](#45-financial-analysis-engine-fr-5xx)
    - [4.6 Data Export (FR-6xx)](#46-data-export-fr-6xx)
5.  [Non-Functional Requirements](#5-non-functional-requirements)
    - [5.1 Performance (NFR-1xx)](#51-performance-nfr-1xx)
    - [5.2 Reliability (NFR-2xx)](#52-reliability-nfr-2xx)
    - [5.3 Scalability (NFR-3xx)](#53-scalability-nfr-3xx)
    - [5.4 Usability (NFR-4xx)](#54-usability-nfr-4xx)
    - [5.5 Maintainability (NFR-5xx)](#55-maintainability-nfr-5xx)
    - [5.6 Security (NFR-6xx)](#56-security-nfr-6xx)
6.  [System Architecture](#6-system-architecture)
    - [6.1 High-Level Architecture Diagram](#61-high-level-architecture-diagram)
    - [6.2 Component Responsibilities](#62-component-responsibilities)
    - [6.3 Data Flow Diagrams](#63-data-flow-diagrams)
7.  [Data Model](#7-data-model)
    - [7.1 Entity Relationship Diagram](#71-entity-relationship-diagram)
    - [7.2 Complete DDL](#72-complete-ddl)
    - [7.3 Financial Statement Data Schema (JSONB)](#73-financial-statement-data-schema-jsonb)
    - [7.4 Vector Store Schema (Qdrant)](#74-vector-store-schema-qdrant)
8.  [API Specification](#8-api-specification)
    - [8.1 General Conventions](#81-general-conventions)
    - [8.2 Endpoints](#82-endpoints)
9.  [Ingestion Pipeline](#9-ingestion-pipeline)
    - [9.1 Pipeline Stages](#91-pipeline-stages)
    - [9.2 Document Parsing Rules](#92-document-parsing-rules)
    - [9.3 Section Splitting Rules](#93-section-splitting-rules)
    - [9.4 Chunking Strategy](#94-chunking-strategy)
    - [9.5 Financial Data Extraction](#95-financial-data-extraction)
    - [9.6 Embedding Configuration](#96-embedding-configuration)
10. [RAG Chat Agent](#10-rag-chat-agent)
    - [10.1 System Prompt](#101-system-prompt)
    - [10.2 Retrieval Configuration](#102-retrieval-configuration)
    - [10.3 Prompt Construction](#103-prompt-construction)
    - [10.4 LLM Configuration](#104-llm-configuration)
11. [Financial Analysis Engine](#11-financial-analysis-engine)
    - [11.1 Built-in Formula Registry](#111-built-in-formula-registry)
    - [11.2 Custom Formula DSL](#112-custom-formula-dsl)
    - [11.3 Expression Parser Specification](#113-expression-parser-specification)
    - [11.4 Trend Detection Algorithm](#114-trend-detection-algorithm)
    - [11.5 Scoring Rules](#115-scoring-rules)
12. [Frontend Specification](#12-frontend-specification)
    - [12.1 Page Structure](#121-page-structure)
    - [12.2 Key Pages](#122-key-pages)
    - [12.3 Chat Interface Specification](#123-chat-interface-specification)
13. [Technology Stack](#13-technology-stack)
    - [13.1 Backend](#131-backend)
    - [13.2 Frontend](#132-frontend)
    - [13.3 Data Infrastructure](#133-data-infrastructure)
    - [13.4 External Services](#134-external-services)
14. [Infrastructure & Deployment](#14-infrastructure--deployment)
    - [14.1 Docker Compose](#141-docker-compose-development--single-server-production)
    - [14.2 Backend Dockerfile](#142-backend-dockerfile)
    - [14.3 Frontend Dockerfile](#143-frontend-dockerfile)
    - [14.4 Resource Requirements](#144-resource-requirements)
    - [14.5 Backup Strategy](#145-backup-strategy)
15. [Security](#15-security)
    - [15.1 Authentication (V1)](#151-authentication-v1)
    - [15.2 Input Validation](#152-input-validation)
    - [15.3 LLM Prompt Security](#153-llm-prompt-security)
16. [Testing Strategy](#16-testing-strategy)
17. [Observability & Monitoring](#17-observability--monitoring)
    - [17.1 Structured Logging](#171-structured-logging)
    - [17.2 Metrics](#172-metrics)
    - [17.3 Monitoring Dashboard (Optional)](#173-monitoring-dashboard-optional)
18. [Error Handling & Resilience](#18-error-handling--resilience)
    - [18.1 Error Taxonomy](#181-error-taxonomy)
    - [18.2 Retry Policies](#182-retry-policies)
    - [18.3 Circuit Breaker Pattern](#183-circuit-breaker-pattern)
19. [Configuration Management](#19-configuration-management)
    - [19.1 Environment Variables](#191-environment-variables)
    - [19.2 Configuration Validation](#192-configuration-validation)
20. [Implementation Phases & Milestones](#20-implementation-phases--milestones)
21. [Appendices](#21-appendices)

---

## 1. Executive Summary

### 1.1 Problem Statement

Individual investors and small fund analysts who evaluate public companies face two core challenges:

1. **Information Overload:** SEC filings (10-K, 10-Q) are dense, 100–300 page documents. A 10-year analysis of a single company requires reading 50+ filings comprising thousands of pages. Extracting insights about business direction, risk changes, and strategic shifts requires significant time.

2. **Inconsistent Quantitative Analysis:** Evaluating financial health requires computing dozens of metrics (margins, returns, leverage ratios, growth rates) across multiple years, comparing them against personal investment thresholds, and identifying trends. Doing this manually in spreadsheets is error-prone and time-consuming, especially when comparing multiple companies.

### 1.2 Solution

A self-hosted platform that:

- **Stores and indexes** SEC filings per company, organized by type and period.
- **Provides an AI conversational agent** (per company) that has "read" all uploaded filings and can answer qualitative questions about the business, risks, strategy, competitive position, and changes over time — always grounding answers in specific filings.
- **Automates quantitative analysis** by extracting structured financial data from filings, computing user-defined financial metrics/ratios, comparing them against user-defined thresholds, and producing a scored report card.

### 1.3 Key Design Principles

| Principle | Description |
| :-- | :-- |
| Company-scoped | All data, chat, and analysis is organized per-company. The company is the central entity. |
| User-defined criteria | The financial scoring system is fully configurable. Users define what to measure, how to compute it, what thresholds to apply, and how to weight each criterion. |
| Grounded AI | The chat agent must ONLY answer based on uploaded filings. It must cite sources. It must refuse to speculate beyond the data. |
| Self-hosted | The platform runs on user's own infrastructure (local Docker or cloud VPS). Only outbound calls are to LLM APIs and SEC EDGAR. |
| Single user | V1 is designed for a single analyst. Authentication is simple (API key or basic auth). Multi-user is a future consideration. |
| Offline-capable data | Once filings are ingested, all analysis and chat works without re-fetching from SEC. Only LLM inference requires external API calls. |

---

## 2. Glossary & Definitions

| Term | Definition |
| :-- | :-- |
| 10-K | Annual report filed by public companies with the SEC. Contains business overview, risk factors, financial statements, MD&A, and more. Organized into Items 1–15. |
| 10-Q | Quarterly report (filed for Q1, Q2, Q3; Q4 is covered by 10-K). Smaller scope than 10-K, focuses on interim financial statements and updates. |
| 8-K | Current report for material events (acquisitions, leadership changes, etc.). Optional support in V1. |
| CIK | Central Index Key — SEC's unique identifier for each filing entity. Example: Apple Inc = `0000320193`. |
| Accession Number | SEC's unique identifier for each individual filing. Format: `0000320193-24-000123`. |
| EDGAR | Electronic Data Gathering, Analysis, and Retrieval — SEC's filing system and public API. |
| XBRL | eXtensible Business Reporting Language — structured data format embedded in SEC filings. Enables machine-readable extraction of financial line items. |
| RAG | Retrieval-Augmented Generation — pattern where relevant documents are retrieved and injected into LLM context to ground responses in factual data. |
| Chunk | A segment of text (typically 512–1024 tokens) created by splitting a larger document. Chunks are embedded and stored in the vector database for semantic search. |
| Embedding | A dense vector representation of text (typically 1536–3072 dimensions) that captures semantic meaning. Similar texts have similar embeddings. |
| Vector Store | A database optimized for storing and searching high-dimensional vectors by similarity (cosine distance, dot product). |
| Analysis Profile | A user-defined collection of financial criteria with thresholds, used to score/evaluate a company. |
| Criterion (pl. Criteria) | A single financial metric within an analysis profile. Consists of a formula, comparison operator, threshold value(s), and weight. |
| Formula | A named computation that takes structured financial data as input and produces a numeric value. Example: `roe = Net Income / Total Equity`. |
| Filing Period | The time period covered by a filing. Identified by fiscal year and fiscal quarter (`null` for annual). |
| Section | A distinct part of an SEC filing (e.g., Item 1 — Business, Item 1A — Risk Factors, Item 7 — MD&A). |

---

## 3. User Personas & Stories

### 3.1 Primary Persona: Independent Equity Analyst

**Name:** Alex
**Background:** Self-directed investor who manages their own portfolio. Has 5–15 years of investing experience. Follows a value investing or quality-growth investment philosophy. Currently analyzes 20–50 companies per year by reading SEC filings and building spreadsheet models.

**Pain Points:**

- Spends 4–8 hours per company reading annual reports
- Maintaining spreadsheets for financial metrics across companies is tedious
- Difficulty remembering specific details from filings read months ago
- No systematic way to compare companies against a consistent set of criteria
- Missing important changes in risk factors or business strategy between years

### 3.2 User Stories

#### 3.2.1 Company Management

> **US-010:** As an analyst, I want to **register a new company by ticker symbol** so that I can begin uploading and analyzing its filings.
>
> *Acceptance Criteria:*
> - I provide a ticker (e.g., `"AAPL"`) and the system creates a company record
> - The system auto-populates company name, CIK, sector, and industry from SEC EDGAR
> - If the ticker is already registered, I receive an appropriate error
> - The company appears in my company list immediately

> **US-011:** As an analyst, I want to **see a list of all my tracked companies** with a summary of how many filings are loaded and analysis status.
>
> *Acceptance Criteria:*
> - Each company shows: ticker, name, sector, document count, latest filing date
> - Companies are sortable by name, ticker, or latest filing date
> - I can search/filter the company list

> **US-012:** As an analyst, I want to **view a company detail page** that shows all uploaded filings, financial data availability, and recent chat sessions.
>
> *Acceptance Criteria:*
> - Timeline view of all filings with their ingestion status
> - Summary of available financial data periods
> - Links to start a new chat or open recent sessions
> - Link to run analysis

#### 3.2.2 Document Upload & Ingestion

> **US-020:** As an analyst, I want to **upload an SEC filing** (PDF or HTML) for a specific company and filing period so that the AI can learn from it.
>
> *Acceptance Criteria:*
> - I can select the company, filing type (10-K/10-Q), fiscal year, and quarter
> - I upload a single file (PDF or HTML)
> - The file is stored and queued for processing
> - I see immediate feedback that the upload was received
> - I can track the processing status (`uploaded → parsing → embedding → ready`)

> **US-021:** As an analyst, I want the system to **automatically fetch filings from SEC EDGAR** for a company so I don't have to manually download them.
>
> *Acceptance Criteria:*
> - I specify the company and how many years back to fetch (default: 10)
> - The system queries SEC EDGAR for all 10-K and 10-Q filings for that period
> - Each filing is downloaded, stored, and queued for ingestion
> - I can see progress of the bulk fetch operation
> - Filings that already exist in the system are skipped (no duplicates)
> - The system respects SEC EDGAR rate limits (10 requests/second max)

> **US-022:** As an analyst, I want to **see the ingestion status** of all documents for a company so I know when the system is ready for chat/analysis.
>
> *Acceptance Criteria:*
> - Status displayed per document: `uploaded`, `parsing`, `parsed`, `embedding`, `ready`, `error`
> - For errors, I see the error message and can retry the ingestion
> - Overall company readiness indicator (e.g., "42 of 45 documents ready")

> **US-023:** As an analyst, I want to **re-ingest a document that failed processing** so I can fix transient errors.
>
> *Acceptance Criteria:*
> - Documents in "error" status show a "Retry" action
> - Retrying resets the status and re-runs the full pipeline
> - The original file is preserved (not re-uploaded)

> **US-024:** As an analyst, I want to **delete a document** and all its derived data (chunks, embeddings, financial data) if it was uploaded in error.
>
> *Acceptance Criteria:*
> - Deleting removes: the file from storage, all chunks from vector DB, all section records, associated financial data if it was the sole source
> - Requires confirmation before deletion

#### 3.2.3 AI Chat Agent

> **US-030:** As an analyst, I want to **start a new chat session scoped to a specific company** so I can ask questions about that company's filings.
>
> *Acceptance Criteria:*
> - Chat is always scoped to exactly one company
> - The agent introduces itself and states which filings it has access to
> - The agent knows the company name, ticker, and available filing date range

> **US-031:** As an analyst, I want to **ask the agent qualitative questions** about the company and receive answers grounded in the actual SEC filings.
>
> *Example questions:*
> - "What are the main risk factors for this company?"
> - "How has the business model changed over the last 5 years?"
> - "What did management say about competition in the 2023 10-K?"
> - "Compare the revenue segments between 2020 and 2024"
> - "What are the key items in their litigation disclosures?"
>
> *Acceptance Criteria:*
> - Answers reference specific filings (e.g., "According to the FY2023 10-K, Item 1A…")
> - The agent uses information from multiple filings when appropriate
> - The agent clearly states when information is not available in the filings
> - Responses stream in real-time (token by token)

> **US-032:** As an analyst, I want the agent to **refuse to answer questions that cannot be grounded** in the uploaded filings.
>
> *Acceptance Criteria:*
> - If asked about future predictions, stock price, or buy/sell recommendations, the agent politely declines and explains its scope
> - If the question requires data not in the filings, the agent says so
> - The agent never fabricates financial numbers

> **US-033:** As an analyst, I want to **see which filing sections were used** to generate each response so I can verify the information.
>
> *Acceptance Criteria:*
> - Each response includes a "Sources" section listing the retrieved chunks
> - Sources show: document type, fiscal year/quarter, section title, relevance score
> - I can click a source to see the full chunk text

> **US-034:** As an analyst, I want to **continue a previous chat session** so I can build on earlier conversations.
>
> *Acceptance Criteria:*
> - I can see a list of past sessions with title and last message date
> - Opening a session loads the full message history
> - New messages are added to the same session with full context

> **US-035:** As an analyst, I want the agent to **handle follow-up questions** that reference previous messages in the conversation.
>
> *Acceptance Criteria:*
> - "What about their international revenue?" after discussing revenue segments correctly interprets "their" as the company being discussed
> - Conversation context window includes last 10 exchanges (configurable)

#### 3.2.4 Financial Analysis

> **US-040:** As an analyst, I want to **create an analysis profile with my custom criteria** so I can score companies consistently.
>
> *Acceptance Criteria:*
> - I define a profile name and description
> - I add 1–30 criteria, each with: name, category, formula, comparison, threshold(s), weight, and lookback period
> - I can choose from a library of built-in formulas or define custom ones
> - I can mark a profile as my default

> **US-041:** As an analyst, I want to **run my analysis profile against a company** and see a scored report card.
>
> *Acceptance Criteria:*
> - Each criterion shows: computed values by year, latest value, threshold, pass/fail status, and trend (improving/declining/stable)
> - Overall weighted score is computed and displayed as percentage
> - Results are color-coded: green (pass), red (fail), yellow (borderline)
> - Results are saved and can be viewed later without re-running

> **US-042:** As an analyst, I want to see **historical values for each metric charted over time** so I can visualize trends.
>
> *Acceptance Criteria:*
> - Line chart showing metric values across years
> - Threshold displayed as a horizontal reference line
> - Clear labeling of passing vs. failing years

> **US-043:** As an analyst, I want to **compare two or more companies side by side** using the same analysis profile.
>
> *Acceptance Criteria:*
> - I select 2–10 companies and one analysis profile
> - A comparison table shows each criterion value for each company
> - Companies are ranked by overall score
> - Color coding shows pass/fail per cell

> **US-044:** As an analyst, I want the system to **generate an AI narrative summary** of the analysis results explaining the key findings.
>
> *Acceptance Criteria:*
> - Summary highlights strengths (consistently passing criteria)
> - Summary flags concerns (failing criteria, declining trends)
> - Summary notes any data gaps or insufficient history
> - Summary is stored with the analysis results

> **US-045:** As an analyst, I want to **edit my analysis profile** (add/remove/modify criteria) and re-run analysis to see updated results.
>
> *Acceptance Criteria:*
> - Changes to a profile create a new version (old results reference old version)
> - Re-running produces a new result set with the updated criteria

> **US-046:** As an analyst, I want to **define custom formulas** using a simple expression syntax when the built-in formulas don't cover my needs.
>
> *Acceptance Criteria:*
> - I can write expressions like:
>   `"income_statement.operating_income / (balance_sheet.total_assets - balance_sheet.total_current_liabilities)"`
> - The expression parser supports: `+`, `-`, `*`, `/`, parentheses, `abs()`, `min()`, `max()`
> - Field references use dot notation into the `financial_statements` JSON structure
> - Invalid expressions produce clear error messages at profile save time
> - Custom formulas can reference previous period data with `prev()` wrapper:
>   `"(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)"`

#### 3.2.5 Data Export

> **US-050:** As an analyst, I want to **export analysis results to a PDF report** so I can share findings or keep offline records.
>
> *Acceptance Criteria:*
> - PDF includes: company info, analysis profile summary, scored criteria table, trend charts, AI narrative summary
> - Professional formatting with header, date, and company branding

> **US-051:** As an analyst, I want to **export raw financial data to CSV/Excel** so I can do additional analysis in my own tools.
>
> *Acceptance Criteria:*
> - Export includes all available financial statement data for selected periods
> - Columns: metric name, and one column per fiscal year/quarter
> - Available for download via API and UI

---

## 4. Functional Requirements

### 4.1 Company Management (FR-1xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-100 | System SHALL allow creating a company record with at minimum a ticker symbol | Must |
| FR-101 | System SHALL auto-resolve company name, CIK, sector, and industry from SEC EDGAR when a ticker is provided | Must |
| FR-102 | System SHALL enforce unique ticker constraint (no duplicate companies) | Must |
| FR-103 | System SHALL allow listing all companies with summary statistics | Must |
| FR-104 | System SHALL allow updating company metadata (name, sector, etc.) | Should |
| FR-105 | System SHALL allow deleting a company and ALL associated data (documents, chunks, financials, chats, results) with confirmation | Should |
| FR-106 | System SHALL support searching/filtering companies by ticker, name, or sector | Should |

### 4.2 Document Management (FR-2xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-200 | System SHALL accept file uploads in PDF and HTML formats | Must |
| FR-201 | System SHALL accept filing metadata: `doc_type` (10-K, 10-Q, 8-K), `fiscal_year`, `fiscal_quarter`, `filing_date`, `period_end_date` | Must |
| FR-202 | System SHALL store uploaded files in object storage (S3/MinIO) organized by `company_id/doc_type/year/` | Must |
| FR-203 | System SHALL prevent duplicate uploads (same company + doc_type + fiscal_year + fiscal_quarter) | Must |
| FR-204 | System SHALL track document processing status: `uploaded → parsing → parsed → embedding → ready → error` | Must |
| FR-205 | System SHALL support automatic fetching of filings from SEC EDGAR given a company CIK and year range | Must |
| FR-206 | System SHALL respect SEC EDGAR rate limits (max 10 requests/second, `User-Agent` header required) | Must |
| FR-207 | System SHALL extract text from PDF files preserving paragraph structure | Must |
| FR-208 | System SHALL extract text from HTML filings (stripping formatting, preserving content structure) | Must |
| FR-209 | System SHALL split extracted text into SEC filing sections (Items) using pattern matching | Must |
| FR-210 | System SHALL support re-processing a document from any failed stage | Should |
| FR-211 | System SHALL support deletion of individual documents with cascade cleanup | Should |
| FR-212 | System SHALL report file size, page count, and token count per document | Should |
| FR-213 | System SHALL support 8-K filings as an optional document type | Could |
| FR-214 | System SHALL support 20-F filings (foreign private issuers) as an optional document type | Could |

### 4.3 Ingestion Pipeline (FR-3xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-300 | System SHALL chunk document sections into segments of 512–1024 tokens with 10–20% overlap | Must |
| FR-301 | System SHALL generate vector embeddings for each chunk using a configurable embedding model | Must |
| FR-302 | System SHALL store embeddings in a vector database in a company-scoped namespace/collection | Must |
| FR-303 | System SHALL attach metadata to each vector: `company_id`, `document_id`, `doc_type`, `fiscal_year`, `fiscal_quarter`, `section_key`, `section_title`, `filing_date` | Must |
| FR-304 | System SHALL extract structured financial data from filings using SEC XBRL API (`companyfacts` endpoint) | Must |
| FR-305 | System SHALL map XBRL US-GAAP taxonomy tags to internal financial data schema | Must |
| FR-306 | System SHALL store structured financial data as JSON in PostgreSQL, keyed by company + period | Must |
| FR-307 | System SHALL process ingestion asynchronously (not blocking the API request) | Must |
| FR-308 | System SHALL support processing multiple documents concurrently (configurable worker count) | Should |
| FR-309 | System SHALL emit progress events during ingestion (for status tracking) | Should |
| FR-310 | System SHALL handle malformed/corrupt PDFs gracefully with clear error messages | Must |
| FR-311 | System SHALL deduplicate chunks that are identical within the same document | Should |

### 4.4 Chat Agent (FR-4xx)

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
| FR-409 | System SHALL support configurable retrieval parameters: `top_k` (default 15), `score_threshold` (default 0.65) | Should |
| FR-410 | System SHALL support filtering retrieval by date range, document type, or section | Should |
| FR-411 | System SHALL auto-generate session titles based on the first user message | Should |
| FR-412 | System SHALL support deleting chat sessions | Should |
| FR-413 | System SHALL handle the case where no relevant chunks are found (inform user, suggest rephrasing) | Must |

### 4.5 Financial Analysis Engine (FR-5xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-500 | System SHALL provide a library of at least 20 built-in financial formulas (see [Appendix A](appendices/appendix-a-builtin-formulas.md)) | Must |
| FR-501 | System SHALL allow creating analysis profiles containing 1–30 criteria | Must |
| FR-502 | System SHALL support comparison operators: `>`, `>=`, `<`, `<=`, `=`, `between`, `trend_up`, `trend_down` | Must |
| FR-503 | System SHALL support numeric thresholds (single value, or low/high range for `"between"`) | Must |
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

### 4.6 Data Export (FR-6xx)

| ID | Requirement | Priority |
| :-- | :-- | :-- |
| FR-600 | System SHALL support exporting financial data to CSV format | Should |
| FR-601 | System SHALL support exporting analysis results to JSON format | Must |
| FR-602 | System SHALL support generating a PDF analysis report | Could |
| FR-603 | System SHALL support exporting chat session transcripts | Could |

---

## 5. Non-Functional Requirements

### 5.1 Performance (NFR-1xx)

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

### 5.2 Reliability (NFR-2xx)

| ID | Requirement | Target |
| :-- | :-- | :-- |
| NFR-200 | Ingestion pipeline SHALL be idempotent (re-running produces same result) | Must |
| NFR-201 | Failed ingestion steps SHALL be retryable without data corruption | Must |
| NFR-202 | System SHALL not lose uploaded files even if ingestion fails | Must |
| NFR-203 | Database operations SHALL use transactions for multi-step mutations | Must |
| NFR-204 | System SHALL gracefully degrade if LLM API is unavailable (chat unavailable, analysis still works) | Should |
| NFR-205 | System SHALL gracefully degrade if vector store is unavailable (chat unavailable, CRUD still works) | Should |

### 5.3 Scalability (NFR-3xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-300 | System is designed for single-user deployment but should support multiple concurrent browser tabs/sessions | Must |
| NFR-301 | Worker pool size SHALL be configurable (1–10 workers) | Must |
| NFR-302 | Vector store collections SHALL be partitioned per company to allow independent scaling | Must |
| NFR-303 | Financial data storage SHALL use JSONB for flexibility but with indexed query paths | Should |

### 5.4 Usability (NFR-4xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-400 | Web UI SHALL be responsive (desktop-first, functional on tablet) | Should |
| NFR-401 | Chat interface SHALL display streaming responses character-by-character | Must |
| NFR-402 | All loading states SHALL show progress indicators | Must |
| NFR-403 | Error states SHALL display human-readable messages with suggested actions | Must |
| NFR-404 | Financial figures SHALL be formatted with appropriate precision and units (e.g., `"$394.3B"`, `"48.2%"`) | Must |

### 5.5 Maintainability (NFR-5xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-500 | Code SHALL follow consistent formatting (Black for Python, Prettier for TypeScript) | Must |
| NFR-501 | All public functions/methods SHALL have docstrings/JSDoc | Must |
| NFR-502 | Database schema changes SHALL use versioned migrations (Alembic) | Must |
| NFR-503 | Configuration SHALL be environment-variable driven (12-factor app) | Must |
| NFR-504 | All service dependencies SHALL be injected (not hard-coded) for testability | Must |

### 5.6 Security (NFR-6xx)

| ID | Requirement | Notes |
| :-- | :-- | :-- |
| NFR-600 | API SHALL require authentication (API key in header for V1) | Must |
| NFR-601 | Uploaded files SHALL be validated (file type, size limits) | Must |
| NFR-602 | All user inputs SHALL be sanitized before database queries | Must |
| NFR-603 | LLM prompts SHALL be constructed server-side (user input is never directly used as system prompt) | Must |
| NFR-604 | API keys and secrets SHALL never appear in logs or responses | Must |
| NFR-605 | File upload size limit SHALL be configurable (default: 50MB per file) | Must |
| NFR-606 | Rate limiting SHALL be applied to API endpoints (default: 100 req/min for CRUD, 20 req/min for chat) | Should |

---

## 6. System Architecture

### 6.1 High-Level Architecture Diagram

```text
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
```

### 6.2 Component Responsibilities

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

### 6.3 Data Flow Diagrams

#### 6.3.1 Document Upload & Ingestion Flow

```text
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
```

#### 6.3.2 Chat Flow

```text
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
```

#### 6.3.3 Analysis Flow

```text
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
```

---

## 7. Data Model

### 7.1 Entity Relationship Diagram

```text
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
```

### 7.2 Complete DDL

> 📎 The full database schema DDL (extensions, enums, all tables, indexes, constraints, and triggers) has been extracted to a separate file for readability.
>
> **→ See [Database Schema DDL](appendices/database-schema-ddl.md)**

### 7.3 Financial Statement Data Schema (JSONB)

The `statement_data` JSONB column in `financial_statements` follows this schema:

```json
{
  "income_statement": {
    "revenue": 394328000000,
    "cost_of_revenue": 223546000000,
    "gross_profit": 170782000000,
    "research_and_development": 29915000000,
    "selling_general_admin": 24932000000,
    "operating_expenses": 54847000000,
    "operating_income": 115935000000,
    "interest_expense": 3933000000,
    "interest_income": 3999000000,
    "other_income_expense": 66000000,
    "income_before_tax": 116001000000,
    "income_tax_expense": 19006000000,
    "net_income": 96995000000,
    "eps_basic": 6.16,
    "eps_diluted": 6.13,
    "shares_outstanding_basic": 15744231000,
    "shares_outstanding_diluted": 15812547000,
    "ebitda": null,
    "depreciation_amortization": 11519000000
  },
  "balance_sheet": {
    "cash_and_equivalents": 29965000000,
    "short_term_investments": 35228000000,
    "accounts_receivable": 60932000000,
    "inventory": 6331000000,
    "total_current_assets": 143566000000,
    "property_plant_equipment": 43715000000,
    "goodwill": 0,
    "intangible_assets": 0,
    "long_term_investments": 100544000000,
    "total_assets": 352583000000,
    "accounts_payable": 62611000000,
    "short_term_debt": 15807000000,
    "total_current_liabilities": 153982000000,
    "long_term_debt": 98959000000,
    "total_liabilities": 290437000000,
    "common_stock": 73812000000,
    "retained_earnings": -214000000,
    "treasury_stock": 0,
    "total_equity": 62146000000,
    "book_value_per_share": null
  },
  "cash_flow": {
    "operating_cash_flow": 110543000000,
    "depreciation_in_cfo": 11519000000,
    "stock_based_compensation": 10833000000,
    "capital_expenditure": -10959000000,
    "acquisitions": 0,
    "investment_purchases": -29513000000,
    "investment_sales": 29917000000,
    "investing_cash_flow": -7077000000,
    "debt_issued": 0,
    "debt_repaid": -11151000000,
    "dividends_paid": -14841000000,
    "share_buybacks": -77550000000,
    "financing_cash_flow": -103362000000,
    "free_cash_flow": 99584000000,
    "net_change_in_cash": 104000000
  }
}
```

### 7.4 Vector Store Schema (Qdrant)

```yaml
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
```

---

## 8. API Specification

### 8.1 General Conventions

```yaml
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
```

### 8.2 Endpoints

#### 8.2.1 Companies

```yaml
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
```

#### 8.2.2 Documents

```yaml
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
```

#### 8.2.3 Chat

```yaml
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
```

#### 8.2.4 Analysis

```yaml
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
```

#### 8.2.5 Financial Data

```yaml
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
```

#### 8.2.6 System

```yaml
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
```

---

## 9. Ingestion Pipeline

### 9.1 Pipeline Stages

```text
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
```

### 9.2 Document Parsing Rules

| Format | Parser | Notes |
| :-- | :-- | :-- |
| PDF | PyMuPDF (fitz) | Extract text page by page. Preserve paragraph breaks. Handle multi-column layouts. |
| HTML | BeautifulSoup + custom cleaner | Strip tags, normalize whitespace, preserve table structure as markdown, handle SEC-specific HTML quirks (nested tables, inline styles). |

**Cleaning rules:**

- Remove page headers/footers (page numbers, repeating company name)
- Normalize Unicode (smart quotes → straight quotes, em-dashes → hyphens)
- Collapse multiple blank lines to single blank line
- Remove table of contents pages (detect by pattern of dotted leaders + page numbers)
- Preserve table data as pipe-delimited markdown tables
- Remove image alt-text and figure references

### 9.3 Section Splitting Rules

**10-K Sections:**

| Section Key | Pattern (regex) | Significance |
| :-- | :-- | :-- |
| `item_1` | `Item\s+1[.\s].*Business` | Company description, products, markets |
| `item_1a` | `Item\s+1A[.\s].*Risk\s+Factors` | Key business and market risks |
| `item_1b` | `Item\s+1B[.\s].*Unresolved` | SEC staff comments |
| `item_1c` | `Item\s+1C[.\s].*Cyber` | Cybersecurity (new, post-2023) |
| `item_2` | `Item\s+2[.\s].*Properties` | Physical assets |
| `item_3` | `Item\s+3[.\s].*Legal` | Litigation |
| `item_5` | `Item\s+5[.\s].*Market` | Stock info, dividends |
| `item_6` | `Item\s+6[.\s].*(?:Selected\|Reserved)` | Historical selected data (now reserved) |
| `item_7` | `Item\s+7[.\s].*Management` | MD&A — most important narrative section |
| `item_7a` | `Item\s+7A[.\s].*Quantitative` | Market risk disclosures |
| `item_8` | `Item\s+8[.\s].*Financial\s+Statements` | Full financial statements + notes |
| `item_9a` | `Item\s+9A[.\s].*Controls` | Internal controls |

**Disambiguation strategy:** When a section header appears multiple times (e.g., in table of contents AND actual section), take the **LAST** occurrence, as the TOC typically comes first.

10-Q Sections follow Part I / Part II structure with a subset of items.

### 9.4 Chunking Strategy

```yaml
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
```

### 9.5 Financial Data Extraction

**Primary source:** SEC EDGAR XBRL `companyfacts` API

- **Endpoint:** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json`
- Returns ALL historical XBRL-tagged financial data for a company
- One API call gets all years and quarters

**XBRL Tag Mapping:** See [Appendix B](appendices/appendix-b-xbrl-tag-mapping.md) for complete mapping of 60+ tags.

**Fallback:** If XBRL data is insufficient (older filings, foreign issuers), the system should:

1. Log a warning indicating which fields are missing
2. Store whatever is available
3. Not block the rest of the ingestion pipeline

### 9.6 Embedding Configuration

```yaml
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
```

---

## 10. RAG Chat Agent

### 10.1 System Prompt

```text
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
```

### 10.2 Retrieval Configuration

```yaml
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
```

### 10.3 Prompt Construction

Messages sent to the LLM:

```text
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
```

### 10.4 LLM Configuration

```yaml
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
```

---

## 11. Financial Analysis Engine

### 11.1 Built-in Formula Registry

See [Appendix A — Built-in Financial Formulas](appendices/appendix-a-builtin-formulas.md) for the complete list of 25+ built-in formulas.

### 11.2 Custom Formula DSL

```yaml
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
      (balance_sheet.total_assets - balance_sheet.total_current_liabilities
       - balance_sheet.cash_and_equivalents)

  - name: "Revenue CAGR 3Y"
    expression: >
      (income_statement.revenue / prev(income_statement.revenue, 3)) ^ (1/3) - 1

  - name: "Capex to Revenue"
    expression: >
      abs(cash_flow.capital_expenditure) / income_statement.revenue
```

### 11.3 Expression Parser Specification

```yaml
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
```

### 11.4 Trend Detection Algorithm

```python
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
```

### 11.5 Scoring Rules

```yaml
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
```

---

## 12. Frontend Specification

### 12.1 Page Structure

```text
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
```

### 12.2 Key Pages

```yaml
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
```

### 12.3 Chat Interface Specification

```yaml
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
```

---

## 13. Technology Stack

### 13.1 Backend

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

### 13.2 Frontend

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

### 13.3 Data Infrastructure

| Component | Technology | Version | Justification |
| :-- | :-- | :-- | :-- |
| Relational DB | PostgreSQL | 16+ | JSONB, robust, extensible |
| Vector DB | Qdrant | 1.9+ | Purpose-built vector search, payload filtering, collections |
| Object Storage | MinIO | latest | S3-compatible, self-hosted |
| Cache/Broker | Redis | 7+ | Celery broker, caching, rate limiting |

### 13.4 External Services

| Service | Purpose | Required |
| :-- | :-- | :-- |
| OpenAI API | Embeddings (`text-embedding-3-large`) + Chat (`gpt-4o`) | Yes |
| SEC EDGAR API | Company info, filing index, XBRL data | Yes (free, no key needed) |
| Anthropic API | Alternative LLM (Claude) | No (optional) |

---

## 14. Infrastructure & Deployment

### 14.1 Docker Compose (Development & Single-Server Production)

```yaml
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
```

### 14.2 Backend Dockerfile

```dockerfile
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
```

### 14.3 Frontend Dockerfile

```dockerfile
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
```

### 14.4 Resource Requirements

```yaml
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
```

### 14.5 Backup Strategy

```yaml
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
```

---

## 15. Security

### 15.1 Authentication (V1)

```yaml
authentication:
  method: API Key
  header: X-API-Key
  storage: environment variable (API_KEY)
  validation: constant-time string comparison
  
  # API key is set during deployment via .env
  # All API endpoints except /health require valid API key
  # Frontend embeds API key in requests (acceptable for single-user self-hosted)
  
  # Future (V2): JWT with user accounts, OAuth2
```

### 15.2 Input Validation

```yaml
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
```

### 15.3 LLM Prompt Security

- User message is **ALWAYS** placed in the designated user content section
- User message **NEVER** appears in the system prompt
- System prompt is hardcoded server-side (not user-modifiable)
- Retrieved context is clearly delimited from user input in the prompt
- The agent is instructed to refuse off-topic requests
- No tool-use / function-calling that could access system resources

---

## 16. Testing Strategy

The testing strategy follows a standard pyramid: **70% unit tests**, **25% integration tests**, **5% E2E tests**.

```text
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
```

> 📎 The full testing strategy — including detailed unit test cases, integration test suites, E2E journey definitions, performance tests, test fixtures, CI/CD pipeline configuration, and `pytest` settings — has been extracted to a separate file for readability.
>
> **→ See [Testing Strategy — Detailed](appendices/testing-strategy-detailed.md)**

---

## 17. Observability & Monitoring

### 17.1 Structured Logging

```yaml
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
```

### 17.2 Metrics

```yaml
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
```

### 17.3 Monitoring Dashboard (Optional)

```yaml
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
```

---

## 18. Error Handling & Resilience

### 18.1 Error Taxonomy

```yaml
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
```

### 18.2 Retry Policies

```yaml
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
```

### 18.3 Circuit Breaker Pattern

```yaml
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
```

---

## 19. Configuration Management

### 19.1 Environment Variables

```bash
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
```

### 19.2 Configuration Validation

```python
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
```

---

## 20. Implementation Phases & Milestones

### Phase 1: Foundation (Core Infrastructure)

**Milestone:** "System boots up and stores data"
**Duration estimate:** 3–5 days

**Deliverables:**

- Project scaffolding (monorepo structure)
- Docker Compose with all services
- FastAPI application skeleton with health check
- PostgreSQL schema + Alembic migrations
- Pydantic models for all entities
- Company CRUD API (create, list, get, update, delete)
- MinIO integration (bucket creation, file upload/download)
- Configuration management (`.env` loading, validation)
- Authentication middleware (API key)
- Error handling middleware
- Structured logging setup
- Unit tests for company service
- Integration tests for company API

**Verification:**

- `docker compose up` creates all services
- `GET /health` returns healthy status
- `POST/GET/PUT/DELETE /companies` works
- Alembic migrations run cleanly

---

### Phase 2: Ingestion Pipeline

**Milestone:** "Documents can be uploaded, parsed, chunked, and embedded"
**Duration estimate:** 5–7 days

**Deliverables:**

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

**Verification:**

- Upload PDF → status progresses to "ready"
- Chunks visible in Qdrant dashboard
- Section records in database match expected sections
- Token counts are accurate
- Duplicate upload returns 409

---

### Phase 3: SEC EDGAR Integration

**Milestone:** "Automatic filing fetch and financial data extraction"
**Duration estimate:** 3–5 days

**Deliverables:**

- SEC EDGAR client (ticker → CIK resolution)
- Filing index fetcher (list available filings for company)
- Filing download (fetch actual filing documents)
- Rate limiting for SEC API calls
- XBRL `companyfacts` API integration
- XBRL tag → internal schema mapping (60+ tags)
- Financial statements storage in PostgreSQL
- Auto-fetch API endpoint
- Celery queue for SEC fetch tasks
- Financial data API endpoint
- CSV export endpoint
- Unit tests for XBRL mapper, SEC client
- Integration tests for full fetch + extract flow

**Verification:**

- Auto-resolve CIK for AAPL → `0000320193`
- Fetch 10-K/10-Q filings for last 5 years
- XBRL data extracted into `financial_statements`
- Financial data API returns structured data
- CSV export is valid and parseable

---

### Phase 4: RAG Chat Agent

**Milestone:** "Conversational AI agent answers questions about company filings"
**Duration estimate:** 5–7 days

**Deliverables:**

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

**Verification:**

- Chat creates session, returns streaming response
- Response contains filing citations
- Sources metadata returned via SSE
- Follow-up questions use conversation context
- Filtered search returns only matching documents
- Session history persists and loads correctly

---

### Phase 5: Financial Analysis Engine

**Milestone:** "Automated financial scoring with user-defined criteria"
**Duration estimate:** 5–7 days

**Deliverables:**

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

**Verification:**

- Create profile with 10 criteria → save succeeds
- Run analysis → returns scored results with pass/fail per criterion
- Custom formula `"income_statement.revenue / balance_sheet.total_assets"` computes correctly
- Trend detection identifies obvious trends correctly
- Multi-company comparison returns ranked results
- AI summary references company and key findings

---

### Phase 6: Frontend Application

**Milestone:** "Full web UI for all platform features"
**Duration estimate:** 7–10 days

**Deliverables:**

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

**Verification:**

- All pages render without errors
- Chat streaming works in browser (tokens appear one by one)
- Document upload via UI triggers processing
- Analysis results display with colors and charts
- Navigation between pages preserves state

---

### Phase 7: Polish & Production Readiness

**Milestone:** "System is production-ready for self-hosted deployment"
**Duration estimate:** 3–5 days

**Deliverables:**

- E2E tests for critical journeys
- Performance testing and optimization
- Production Docker images (multi-stage, non-root)
- Production `docker-compose.yml`
- Backup scripts
- `README.md` with setup instructions
- `DEPLOYMENT.md` with production deployment guide
- Default analysis profile (Value Investor template)
- Seed data script (creates sample profile)
- Rate limiting implementation
- Request validation hardening
- Error message review (user-friendly)
- Log output review (no sensitive data)
- Dependency audit (security)
- Documentation: API reference (auto-generated from FastAPI)

**Verification:**

- Fresh clone → `docker compose up` → fully functional system
- All tests pass in CI
- No security warnings in dependency audit
- Backup and restore cycle works

---

## 21. Appendices

The following reference materials have been extracted into separate files to keep the main specification focused and readable.

| Appendix | Description | Link |
| :-- | :-- | :-- |
| **A** | Built-in Financial Formulas — 25+ formulas across profitability, growth, liquidity, solvency, efficiency, quality, and dividend categories | [appendix-a-builtin-formulas.md](appendices/appendix-a-builtin-formulas.md) |
| **B** | XBRL Tag Mapping — 60+ US-GAAP XBRL tags mapped to internal financial data fields, with alternative tags and period selection rules | [appendix-b-xbrl-tag-mapping.md](appendices/appendix-b-xbrl-tag-mapping.md) |
| **C** | SEC Filing Section Reference — Complete 10-K and 10-Q section definitions with regex patterns and importance ratings | [appendix-c-sec-filing-sections.md](appendices/appendix-c-sec-filing-sections.md) |
| **D** | Default Analysis Profile — "Quality Value Investor" seed profile with 15 criteria | [appendix-d-default-analysis-profile.md](appendices/appendix-d-default-analysis-profile.md) |
| **E** | Project Directory Structure — Full monorepo tree for backend, frontend, tests, and scripts | [appendix-e-project-structure.md](appendices/appendix-e-project-structure.md) |
| **F** | Makefile Commands — Development and operations shortcut commands | [appendix-f-makefile.md](appendices/appendix-f-makefile.md) |
| — | Database Schema DDL — Complete PostgreSQL DDL (extensions, enums, tables, indexes, triggers) | [database-schema-ddl.md](appendices/database-schema-ddl.md) |
| — | Testing Strategy (Detailed) — Unit, integration, E2E, performance tests; fixtures; CI/CD pipeline; pytest config | [testing-strategy-detailed.md](appendices/testing-strategy-detailed.md) |

---

## End of Specification

This document contains all information necessary to implement the **InvestorInsights** Public Company Analysis Platform. An implementor (human or AI) should be able to build the complete system by following this specification without requiring additional clarification.

**Key implementation order:** Follow the phases in [Section 20](#20-implementation-phases--milestones). Each phase builds on the previous one and has clear verification criteria.

When in doubt, the implementor should:

1. Prefer **simplicity** over cleverness
2. Prefer **explicit** over implicit
3. Write tests **before or alongside** implementation
4. Use the exact data models, API signatures, and configurations specified
5. Log decisions that deviate from the spec
