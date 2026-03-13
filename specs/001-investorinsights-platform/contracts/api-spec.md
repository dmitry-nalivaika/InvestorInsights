# API Contract: InvestorInsights Platform

**Spec**: [spec.md](../spec.md)
**Plan**: [plan.md](../plan.md)

---

## General Conventions

```yaml
base_url: /api/v1
content_type: application/json
authentication: X-API-Key header
pagination: offset/limit (response includes total, limit, offset)
error_format:
  status: integer
  error: string
  message: string
  details: object (optional)
date_format: ISO 8601 (YYYY-MM-DD)
datetime_format: ISO 8601 with timezone (YYYY-MM-DDTHH:mm:ssZ)
id_format: UUID v4
```

---

## Companies

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

---

## Documents

```yaml
POST /api/v1/companies/{company_id}/documents:
  description: Upload a filing document
  content_type: multipart/form-data
  request_body:
    file: binary (required, PDF or HTML, max 50MB)
    doc_type: string (required, enum: 10-K, 10-Q, 8-K, 20-F, DEF14A, OTHER)
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
    503: Task broker (Redis) unavailable — document saved with status "uploaded" for later retry (FR-307)

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
  description: Retry failed ingestion — resumes pipeline from the failed stage, not from scratch (FR-210)
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

---

## Chat

```yaml
POST /api/v1/companies/{company_id}/chat:
  description: Send a message and receive streaming AI response
  request_body:
    message: string (required, 1-10000 chars)
    session_id: UUID (optional — creates new session if omitted)
    retrieval_config: (optional)
      top_k: integer (1-50, default: 15)
      score_threshold: float (0-1, default: 0.65)
      query_expansion: boolean (default: true — enable LLM-based query expansion per FR-409)
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

---

## Analysis

```yaml
POST /api/v1/analysis/profiles:
  description: Create an analysis profile
  request_body:
    name: string (required, unique)
    description: string (optional)
    is_default: boolean (default: false)
    criteria: (required, array, 1-30 items)
      - name: string (required)
        category: string (required, enum: profitability, valuation, growth, liquidity, solvency, efficiency, dividend, quality, custom — per FR-516)
        description: string (optional)
        formula: string (required — built-in name or custom expression)
        is_custom_formula: boolean (default: false)
        comparison: string (required, enum: >, >=, <, <=, =, between, trend_up, trend_down — per FR-502)
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
  description: Update profile (increments version). Existing analysis results retain the profile_version snapshot they were computed against; new runs use the incremented version.
  request_body: same as POST
  response: 200 OK

DELETE /api/v1/analysis/profiles/{profile_id}:
  description: Delete profile and criteria (results preserved with snapshot)
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
          grade: string (A|B|C|D|F — per FR-510: A 90–100%, B 75–89%, C 60–74%, D 40–59%, F 0–39%)
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

GET /api/v1/analysis/results/{result_id}/export:
  description: Export a specific analysis result as downloadable JSON
  response: 200 OK (application/json)
    headers:
      Content-Disposition: attachment; filename="{ticker}_{profile}_{date}.json"
    body: Full AnalysisResult object (same shape as GET /results/{result_id})
  errors:
    404: Result not found

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

---

## Financial Data

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

---

## System

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
