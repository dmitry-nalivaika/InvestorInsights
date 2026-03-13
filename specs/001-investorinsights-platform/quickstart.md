# Quickstart: InvestorInsights Platform

**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

---

## Validation Scenarios

These scenarios verify the system works end-to-end after each implementation phase.

---

### Scenario 1: Foundation Boot (Phase 1)

**Validates**: Infrastructure, database, company CRUD, auth, health check.

1. Start local dev environment:
   ```
   docker compose -f docker-compose.dev.yml up
   ```
2. Verify health:
   ```
   curl http://localhost:8000/api/v1/health
   # → {"status": "healthy", "components": {"database": "healthy", ...}}
   ```
3. Register a company (requires API key):
   ```
   curl -X POST http://localhost:8000/api/v1/companies \
     -H "X-API-Key: dev-key" \
     -H "Content-Type: application/json" \
     -d '{"ticker": "AAPL"}'
   # → 201, auto-resolved name="Apple Inc", cik="0000320193"
   ```
4. List companies:
   ```
   curl http://localhost:8000/api/v1/companies -H "X-API-Key: dev-key"
   # → 200, items: [{ticker: "AAPL", name: "Apple Inc", ...}]
   ```
5. Duplicate attempt:
   ```
   curl -X POST http://localhost:8000/api/v1/companies \
     -H "X-API-Key: dev-key" \
     -d '{"ticker": "AAPL"}'
   # → 409 Conflict
   ```

**Pass criteria**: All requests return expected status codes. Health reports all components healthy.

---

### Scenario 2: Document Ingestion (Phase 2)

**Validates**: File upload, parsing, chunking, embedding, status tracking.

1. Upload a 10-K PDF:
   ```
   curl -X POST http://localhost:8000/api/v1/companies/{id}/documents \
     -H "X-API-Key: dev-key" \
     -F "file=@tests/fixtures/simple_10k.pdf" \
     -F "doc_type=10-K" -F "fiscal_year=2024" \
     -F "filing_date=2024-10-30" -F "period_end_date=2024-09-30"
   # → 202 Accepted, document_id returned
   ```
2. Poll status until "ready":
   ```
   curl http://localhost:8000/api/v1/companies/{id}/documents/{doc_id} \
     -H "X-API-Key: dev-key"
   # → status progresses: uploaded → parsing → parsed → embedding → ready
   ```
3. Verify chunks in Qdrant dashboard: `http://localhost:6333/dashboard`
4. Verify sections in database:
   ```
   curl http://localhost:8000/api/v1/companies/{id}/documents/{doc_id} \
     -H "X-API-Key: dev-key"
   # → sections: [{section_key: "item_1", ...}, {section_key: "item_1a", ...}]
   ```

**Pass criteria**: Document reaches "ready" status within 5 minutes. Chunks visible in Qdrant. Sections parsed correctly.

---

### Scenario 3: SEC EDGAR Integration (Phase 3)

**Validates**: Auto-fetch, XBRL extraction, financial data API.

1. Auto-fetch filings:
   ```
   curl -X POST http://localhost:8000/api/v1/companies/{id}/documents/fetch-sec \
     -H "X-API-Key: dev-key" \
     -d '{"filing_types": ["10-K"], "years_back": 5}'
   # → 202, task_id returned
   ```
2. Monitor task progress:
   ```
   curl http://localhost:8000/api/v1/tasks/{task_id} -H "X-API-Key: dev-key"
   # → status: running, progress: {current: 3, total: 5}
   ```
3. Verify financial data extracted:
   ```
   curl http://localhost:8000/api/v1/companies/{id}/financials \
     -H "X-API-Key: dev-key"
   # → periods with income_statement, balance_sheet, cash_flow data
   ```
4. Export CSV:
   ```
   curl http://localhost:8000/api/v1/companies/{id}/financials/export \
     -H "X-API-Key: dev-key" -o financials.csv
   # → Valid CSV with metrics × years
   ```

**Pass criteria**: 5 annual filings fetched and ingested. Financial data for all years available. CSV export valid.

---

### Scenario 4: RAG Chat (Phase 4)

**Validates**: Chat session, retrieval, streaming, citations, history.

1. Start a chat:
   ```
   curl -N http://localhost:8000/api/v1/companies/{id}/chat \
     -H "X-API-Key: dev-key" \
     -d '{"message": "What are the main risk factors for this company?"}'
   # → SSE stream: session event, sources event, token events, done event
   ```
2. Verify source citations in response text (e.g., "According to the FY2024 10-K, Item 1A...")
3. Verify sources metadata returned via SSE `sources` event
4. Send follow-up:
   ```
   curl -N http://localhost:8000/api/v1/companies/{id}/chat \
     -H "X-API-Key: dev-key" \
     -d '{"message": "How have these risks changed over the last 3 years?", "session_id": "{session_id}"}'
   # → Contextual response referencing multiple filings
   ```
5. Test refusal:
   ```
   curl -N http://localhost:8000/api/v1/companies/{id}/chat \
     -H "X-API-Key: dev-key" \
     -d '{"message": "Should I buy this stock?"}'
   # → Polite decline, explains scope
   ```

**Pass criteria**: Streaming works. Citations present. Follow-ups use context. Out-of-scope requests refused.

---

### Scenario 5: Financial Analysis (Phase 5)

**Validates**: Profile creation, analysis execution, scoring, trends, AI summary.

1. Create profile:
   ```
   curl -X POST http://localhost:8000/api/v1/analysis/profiles \
     -H "X-API-Key: dev-key" \
     -d '{"name": "Value Investor", "criteria": [
       {"name": "Gross Margin > 40%", "category": "profitability",
        "formula": "gross_margin", "comparison": ">=", "threshold_value": 0.40,
        "weight": 2.0, "lookback_years": 5},
       {"name": "D/E < 1.0", "category": "solvency",
        "formula": "debt_to_equity", "comparison": "<=", "threshold_value": 1.0,
        "weight": 2.0, "lookback_years": 5}
     ]}'
   # → 201 Created
   ```
2. Run analysis:
   ```
   curl -X POST http://localhost:8000/api/v1/analysis/run \
     -H "X-API-Key: dev-key" \
     -d '{"company_ids": ["{company_id}"], "profile_id": "{profile_id}"}'
   # → 200, results with per-criterion scores, trends, AI summary
   ```
3. Verify: `pct_score` is computed, each criterion has `passed` boolean, `trend` string, `values_by_year` object.

**Pass criteria**: Analysis returns scored results. Trends computed. AI summary generated.

---

### Scenario 6: Full UI Smoke Test (Phase 6)

**Validates**: Frontend renders all pages, streaming chat works in browser.

1. Open `http://localhost:3000` → Dashboard loads with company cards
2. Click a company → Detail page with tabs (Overview, Documents, Financials, Chat, Analysis)
3. Documents tab → Upload a file, see status update
4. Chat tab → Send message, see tokens stream, see sources panel
5. Analysis tab → Select profile, run, see score card with colors and charts
6. Navigate to Analysis Profiles → Create/edit a profile
7. Navigate to Settings → View configuration

**Pass criteria**: All pages render without errors. Chat streaming works in browser. No console errors.
