# InvestorInsights — User Guide

> A complete guide to using the InvestorInsights platform for SEC filing analysis.
> Last updated: 2026-03-14 · Version 1.0.0

---

## Table of Contents

1. [What Is InvestorInsights?](#1-what-is-investorinsights)
2. [Getting Started](#2-getting-started)
3. [Dashboard](#3-dashboard)
4. [Managing Companies](#4-managing-companies)
5. [Company Detail View](#5-company-detail-view)
   - [Overview Tab](#51-overview-tab)
   - [Documents Tab](#52-documents-tab)
   - [Financials Tab](#53-financials-tab)
   - [Chat Tab](#54-chat-tab)
   - [Analysis Tab](#55-analysis-tab)
6. [Analysis Profiles](#6-analysis-profiles)
7. [Multi-Company Comparison](#7-multi-company-comparison)
8. [Settings & System Health](#8-settings--system-health)
9. [Built-in Financial Formulas](#9-built-in-financial-formulas)
10. [Understanding Grades & Scores](#10-understanding-grades--scores)
11. [Tips & Best Practices](#11-tips--best-practices)
12. [FAQ](#12-faq)

---

## 1. What Is InvestorInsights?

InvestorInsights is an AI-powered platform for analysing SEC filings (10-K annual reports, 10-Q quarterly reports, 8-K current reports, and more). It helps you:

- **Manage companies** — Track multiple publicly traded companies by ticker symbol
- **Ingest SEC filings** — Upload documents manually or auto-fetch them from SEC EDGAR
- **Chat with documents** — Ask natural-language questions about a company's filings and get AI-powered answers with source citations
- **Analyse financials** — Run configurable analysis profiles that score companies on 28+ financial metrics
- **Compare companies** — Rank multiple companies side-by-side on the same analysis criteria
- **View financial data** — Browse extracted income statements, balance sheets, and cash flow data with export to CSV

The platform automatically extracts structured financial data from XBRL, chunks documents for semantic search, and uses Azure OpenAI for intelligent question answering.

---

## 2. Getting Started

### Accessing the Platform

Open your web browser and navigate to the InvestorInsights URL provided by your administrator (typically `http://localhost:3000` for local development or your Azure deployment URL).

You will see the **Dashboard** page, which is your home base for the platform.

### Your First Workflow

Here is the recommended workflow when you start using InvestorInsights for the first time:

```
1. Add a company         → Companies page → "Add Company" button
2. Fetch SEC filings     → Company Detail → Documents tab → "Fetch from SEC"
3. Wait for processing   → Documents will show status: UPLOADED → PARSING → READY
4. Chat with filings     → Company Detail → Chat tab → Ask a question
5. Run analysis          → Company Detail → Analysis tab → Select profile → "Run"
6. Compare companies     → Compare page → Select companies → Run comparison
```

---

## 3. Dashboard

The Dashboard is the first page you see when you open InvestorInsights. It provides a bird's-eye view of your entire portfolio.

### Summary Cards

At the top of the Dashboard, four summary cards give you quick stats:

| Card | What It Shows |
|------|---------------|
| **Companies** | Total number of companies you are tracking |
| **Total Documents** | Combined count of all ingested documents across all companies |
| **Ready for Analysis** | Number of companies with 100% data readiness |
| **Avg Readiness** | Average readiness percentage across all companies |

### Company Grid

Below the summary cards, you'll see a grid of company cards. Each card shows:

- **Ticker and name** (e.g., "AAPL — Apple Inc.")
- **Sector** (e.g., "Technology")
- **Document count** — How many filings have been ingested
- **Latest filing date** — When the most recent filing was processed
- **Readiness** — A percentage indicating how ready the company is for analysis (based on available financial data)

Click any company card to go to its **Company Detail** page.

### Quick Actions

- **"Add Company" button** (top right) — Takes you to the Companies page to register a new company

---

## 4. Managing Companies

Navigate to the **Companies** page using the sidebar (Building icon → "Companies").

### Adding a New Company

1. Click the **"Add Company"** button
2. Enter the **ticker symbol** (e.g., `AAPL`, `MSFT`, `GOOGL`)
3. Optionally provide: company name, CIK number, sector, industry
4. Click **"Create"**

> **Tip:** You only need the ticker symbol. InvestorInsights will automatically look up the company's name, CIK number, and other metadata from SEC EDGAR.

### Searching and Filtering

Use the controls at the top of the company list:

- **Search bar** — Type a ticker or company name to filter
- **Sector filter** — Filter by industry sector
- **Sort** — Sort by name, ticker, creation date, or document count

### Editing a Company

1. Click on a company to open its detail page
2. Company metadata (name, sector, industry, description) can be updated through the Overview tab

### Deleting a Company

1. Open the company's detail page
2. Use the delete option
3. **Warning:** Deleting a company removes ALL associated documents, financial data, chat sessions, and analysis results permanently. You will be asked to confirm before deletion.

---

## 5. Company Detail View

Click on any company (from the Dashboard or Companies page) to open its detail view. This is the most feature-rich page in the application, organised into 5 tabs:

### 5.1 Overview Tab

The Overview tab shows:

- **Company information** — Ticker, name, CIK, sector, industry, and description
- **Documents summary** — Total documents, breakdown by status and filing type, year range
- **Financials summary** — Number of financial periods available, year range
- **Recent chat sessions** — Your most recent conversations about this company

This tab gives you a quick snapshot of everything available for the company.

### 5.2 Documents Tab

The Documents tab is where you manage SEC filing documents for the company.

#### Auto-Fetching from SEC EDGAR

The fastest way to get documents is automatic SEC EDGAR fetching:

1. Click **"Fetch from SEC"**
2. Choose filing types to fetch (10-K, 10-Q, 8-K) and how many years back
3. Click **"Fetch"**

The system will:
- Query SEC EDGAR for available filings
- Download each filing automatically
- Process them through the ingestion pipeline (parse → chunk → embed)
- Extract XBRL financial data

This typically takes 1–5 minutes depending on the number of filings.

#### Manual Upload

You can also upload documents manually:

1. Click **"Upload"**
2. Select a PDF or HTML file (max 50 MB)
3. Fill in the filing metadata (type, fiscal year, filing date)
4. Click **"Upload"**

**Supported file types:** PDF and HTML only.

#### Document Status

Each document shows a status badge:

| Status | Meaning |
|--------|---------|
| 🟡 **UPLOADED** | File received, waiting to be processed |
| 🔵 **PARSING** | Text is being extracted from the document |
| 🔵 **CHUNKING** | Text is being split into searchable chunks |
| 🔵 **EMBEDDING** | Chunks are being converted to vector embeddings |
| 🟢 **READY** | Fully processed — available for chat and analysis |
| 🔴 **FAILED** | Processing failed (you can retry) |

#### Retrying Failed Documents

If a document shows **FAILED** status:
1. Click the retry button next to the document
2. The system will re-attempt the entire ingestion pipeline

#### Deleting Documents

Click the delete button on any document to remove it and all its associated chunks and embeddings.

### 5.3 Financials Tab

The Financials tab displays structured financial data extracted from XBRL:

- **Income Statement** — Revenue, gross profit, operating income, net income, EPS
- **Balance Sheet** — Total assets, liabilities, equity, cash, debt
- **Cash Flow** — Operating cash flow, capital expenditures, free cash flow

Data is organised by fiscal year, with the most recent year shown first.

#### Exporting to CSV

Click the **"Export CSV"** button to download all financial data as a spreadsheet-compatible CSV file. This is useful for further analysis in Excel or Google Sheets.

> **Note:** Financial data is automatically extracted when documents are fetched from SEC EDGAR. The XBRL extraction uses 42 standardised tag mappings to normalise data across different companies.

### 5.4 Chat Tab

The Chat tab lets you have AI-powered conversations about the company's SEC filings.

#### Starting a Conversation

1. Type your question in the message box at the bottom
2. Press **Enter** or click **Send**

The AI will:
- Search through all ingested documents to find relevant sections
- Show you the **source chunks** it found (before the answer)
- Stream the response in real-time
- Include **[Source: ...]** citations in the answer

#### What You Can Ask

Good questions to try:

- "What are the main risk factors mentioned in the latest 10-K?"
- "How has revenue changed over the past 3 years?"
- "What does the company say about competition in their industry?"
- "Summarise the management discussion and analysis section"
- "What are the company's major debt obligations?"
- "Describe the company's business segments"

#### What the Chat Cannot Do

The AI is designed specifically for SEC filing analysis. It will politely decline:

- Investment advice ("Should I buy this stock?")
- Stock price predictions
- Topics unrelated to the company's filings (weather, sports, etc.)
- Personal financial advice

#### Managing Chat Sessions

- Each conversation is saved as a **session** with an auto-generated title
- View previous sessions in the session list on the left
- Click a session to load its history and continue the conversation
- Delete sessions you no longer need

#### Source Citations

When the AI answers your question, it cites its sources:

- **Source badges** appear above the answer showing which documents were used
- Each source shows the filing type (10-K, 10-Q), fiscal year, and section
- **[Source: 10-K 2024, Item 1A]** citations appear inline in the response text

This lets you verify the AI's answers against the original filings.

### 5.5 Analysis Tab

The Analysis tab lets you score a company against configurable financial criteria.

#### Running an Analysis

1. Select an **Analysis Profile** from the dropdown (a default profile is pre-loaded)
2. Click **"Run Analysis"**
3. Wait for results (typically a few seconds)

#### Reading Results

After an analysis completes, you'll see:

**Overall Score Card:**
- **Grade** — A letter grade from A (best) to F (worst)
- **Score** — Percentage score (e.g., 78.5%)
- **Criteria passed/failed/no data** — Breakdown of results

**Criteria Detail Table:**
Each row shows one criterion with:

| Column | Description |
|--------|-------------|
| **Name** | What's being measured (e.g., "Gross Margin") |
| **Category** | Profitability, Growth, Liquidity, etc. |
| **Latest Value** | The computed metric value |
| **Threshold** | The pass/fail target (e.g., ">= 0.40") |
| **Pass/Fail** | Green check or red X |
| **Trend** | Improving ↑, Declining ↓, or Stable → |
| **Historical Values** | Values by year |

---

## 6. Analysis Profiles

Navigate to **Analysis Profiles** in the sidebar to create and manage your scoring criteria.

### What Is a Profile?

An analysis profile is a collection of financial criteria that define what "good" looks like for a company. Think of it as a customisable scorecard.

Each profile contains multiple **criteria**, and each criterion specifies:
- A **formula** (what to calculate)
- A **threshold** (what value constitutes a "pass")
- A **weight** (how important this criterion is relative to others)
- A **lookback period** (how many years of history to consider)

### The Default Profile

InvestorInsights comes with a pre-loaded default profile called **"Comprehensive Financial Health"** that includes 20+ criteria across all categories. This is a great starting point.

### Creating a Custom Profile

1. Click **"Create Profile"**
2. Give it a name and description
3. Add criteria:
   - Choose from **28 built-in formulas** (see [Section 9](#9-built-in-financial-formulas))
   - Or write a **custom formula** using the expression language
   - Set the comparison operator (`>=`, `>`, `<=`, `<`, `=`, `between`, `trend_up`, `trend_down`)
   - Set the threshold value
   - Set the weight (default 1.0)
   - Set the lookback period in years (default 5)
4. Click **"Save"**

### Custom Formula Syntax

You can write custom formulas using this syntax:

```
income_statement.revenue                        # Reference a field
income_statement.net_income / income_statement.revenue  # Division
(balance_sheet.total_assets - balance_sheet.total_current_liabilities) # Subtraction
prev(income_statement.revenue)                  # Previous year's value
(income_statement.revenue - prev(income_statement.revenue)) / prev(income_statement.revenue)  # YoY growth
```

**Available field prefixes:**
- `income_statement.` — Revenue, net income, operating income, etc.
- `balance_sheet.` — Total assets, equity, debt, cash, etc.
- `cash_flow.` — Operating cash flow, capex, etc.

**Supported operations:** `+`, `-`, `*`, `/`, `^` (exponent), parentheses, `abs()`, `min()`, `max()`, `avg()`, `prev()`

### Editing and Deleting Profiles

- Click on any profile to view or edit its criteria
- The default profile can be modified but not deleted
- Deleting a profile removes it and all its associated analysis results

---

## 7. Multi-Company Comparison

Navigate to **Compare** in the sidebar to rank multiple companies against each other.

### Running a Comparison

1. **Select companies** — Choose 2 or more companies from the dropdown
2. **Select a profile** — Choose which analysis profile to use for scoring
3. Click **"Compare"**

### Reading the Comparison Table

The comparison produces a **ranked table** with:

- **Rank** — Companies are ranked from best to worst overall score
- **Grade** — Letter grade for each company
- **Overall Score** — Percentage score
- **Per-Criteria Breakdown** — Each criterion shows pass/fail, value, and trend for every company

This makes it easy to see which companies are strongest in profitability, which have the best liquidity, and where each company's weaknesses lie.

### Use Cases

- **Sector comparison** — Compare all companies in the same sector (e.g., "Which tech company has the best margins?")
- **Peer benchmarking** — See how a company stacks up against its competitors
- **Portfolio screening** — Identify the strongest companies across your watchlist

---

## 8. Settings & System Health

Navigate to **Settings** in the sidebar to view system information and health status.

### Health Check

The Settings page shows the health status of all platform components:

| Component | What It Checks |
|-----------|---------------|
| **Database** | PostgreSQL connectivity |
| **Vector Store** | Qdrant search availability |
| **Object Storage** | Azure Blob file storage |
| **Redis** | Cache and task queue |
| **LLM API** | Azure OpenAI availability |

**Status indicators:**
- 🟢 **Healthy** — All components working
- 🟡 **Degraded** — Some components have issues (basic functionality still works)
- 🔴 **Unhealthy** — Critical component failure (database down)

### System Information

The Settings page also displays:
- Application version
- Server uptime
- API endpoint URL

---

## 9. Built-in Financial Formulas

InvestorInsights includes 28 pre-built financial formulas across 7 categories. These can be used in any analysis profile.

### Profitability (6 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `gross_margin` | Gross profit / Revenue | ≥ 40% |
| `operating_margin` | Operating income / Revenue | ≥ 15% |
| `net_margin` | Net income / Revenue | ≥ 10% |
| `roe` | Net income / Total equity (Return on Equity) | ≥ 15% |
| `roa` | Net income / Total assets (Return on Assets) | ≥ 5% |
| `roic` | NOPAT / Invested capital (Return on Invested Capital) | ≥ 10% |

### Growth (4 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `revenue_growth` | Year-over-year revenue change | ≥ 5% |
| `earnings_growth` | Year-over-year net income change | ≥ 5% |
| `operating_income_growth` | Year-over-year operating income change | ≥ 5% |
| `free_cash_flow_growth` | Year-over-year FCF change | ≥ 0% |

### Liquidity (3 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `current_ratio` | Current assets / Current liabilities | ≥ 1.5 |
| `quick_ratio` | (Current assets − Inventory) / Current liabilities | ≥ 1.0 |
| `cash_ratio` | Cash / Current liabilities | ≥ 0.2 |

### Solvency (3 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `debt_to_equity` | Total debt / Total equity | ≤ 1.0 |
| `debt_to_assets` | Total debt / Total assets | ≤ 0.5 |
| `interest_coverage` | Operating income / Interest expense | ≥ 5.0 |

### Efficiency (4 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `asset_turnover` | Revenue / Total assets | ≥ 0.5 |
| `inventory_turnover` | Cost of revenue / Inventory | ≥ 5.0 |
| `receivables_turnover` | Revenue / Accounts receivable | ≥ 8.0 |
| `payables_turnover` | Cost of revenue / Accounts payable | Between 4–12 |

### Cash Flow Quality (4 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `operating_cash_flow_ratio` | Operating cash flow / Revenue | ≥ 0.15 |
| `free_cash_flow_margin` | Free cash flow / Revenue | ≥ 0.10 |
| `capex_to_revenue` | Capital expenditures / Revenue | ≤ 0.15 |
| `cash_conversion` | Operating cash flow / Net income | ≥ 1.0 |

### Dividend (4 formulas)

| Formula | Description | Typical Threshold |
|---------|-------------|-------------------|
| `dividend_payout_ratio` | Dividends / Net income | Between 20–60% |
| `dividend_yield` | Dividends per share / Stock price | ≥ 1.5% |
| `earnings_retention` | 1 − Payout ratio | ≥ 40% |

---

## 10. Understanding Grades & Scores

### How Scoring Works

When you run an analysis, each criterion is evaluated as either **pass** or **fail**:

1. The formula is computed using the company's latest financial data
2. The result is compared against the threshold
3. If it passes: score contribution = **weight** (typically 1.0)
4. If it fails: score contribution = **0**
5. If there's no data: the criterion is **excluded** (doesn't penalise the company)

### Grade Scale

The overall percentage determines the letter grade:

| Grade | Score Range | Interpretation |
|-------|------------|----------------|
| **A** | 90–100% | Excellent financial health |
| **B** | 75–89% | Good financial health |
| **C** | 60–74% | Adequate financial health |
| **D** | 40–59% | Below average — areas of concern |
| **F** | 0–39% | Poor financial health — significant weaknesses |

### Trend Indicators

Each criterion also shows a **trend** based on historical data (last 3–5 years):

| Trend | Meaning |
|-------|---------|
| ↑ **Improving** | Metric is getting better (>3% normalised improvement per year) |
| → **Stable** | Metric is relatively unchanged |
| ↓ **Declining** | Metric is getting worse (>3% normalised decline per year) |

Trends use **ordinary least squares (OLS) regression** on the available data points, so they reflect the overall direction rather than year-to-year noise.

### Handling Missing Data

- If a company doesn't have data for a criterion (e.g., no inventory for a software company), that criterion is marked as **"No Data"** and excluded from scoring
- This means a software company won't be penalised for not having an inventory turnover ratio
- The percentage score is based only on criteria that could be evaluated

---

## 11. Tips & Best Practices

### Getting the Best Results

1. **Fetch multiple years of filings** — Analysis and trends work best with 3–5 years of data. When fetching from SEC, set "years back" to at least 5.

2. **Wait for READY status** — Documents must be fully processed before they appear in chat results or financial data. Check the Documents tab for status.

3. **Start with the default profile** — The "Comprehensive Financial Health" profile covers all major financial metrics. Customise from there.

4. **Be specific in chat** — Instead of "Tell me about the company," try "What were the main risk factors related to supply chain disruptions in the 2024 10-K?"

5. **Check source citations** — The chat AI cites its sources. Always verify important claims by checking the referenced filing sections.

6. **Compare similar companies** — Comparisons are most meaningful between companies in the same industry (e.g., comparing Apple to Microsoft, not Apple to JPMorgan).

7. **Use trends for context** — A company might fail a threshold today but show an improving trend, suggesting it's heading in the right direction.

### Understanding Limitations

- **Financial data accuracy** depends on XBRL data quality from SEC EDGAR. Some companies use non-standard XBRL tags that may not map correctly.
- **Chat answers** are generated by AI and may occasionally be incorrect. Always verify critical information against the original filings.
- **Analysis scores** are based on quantitative metrics only. They don't capture qualitative factors like management quality, competitive moats, or market conditions.
- **Historical data** is limited to what's available in SEC EDGAR's XBRL API, which may not cover older filings.

---

## 12. FAQ

### General

**Q: What types of SEC filings are supported?**
A: InvestorInsights supports 10-K (annual reports), 10-Q (quarterly reports), 8-K (current reports), and other SEC filing types. The auto-fetch feature focuses on 10-K and 10-Q filings by default.

**Q: What file formats can I upload?**
A: PDF and HTML files only, up to 50 MB each.

**Q: How long does document processing take?**
A: Typically 30 seconds to 2 minutes per document, depending on length. SEC auto-fetch for 5 years of filings usually takes 3–5 minutes total.

**Q: Can I use this for non-US companies?**
A: InvestorInsights is designed for companies that file with the US SEC. It relies on SEC EDGAR for auto-fetch and XBRL data, so companies not filing with the SEC won't have auto-fetch or structured financial data. However, you can manually upload any PDF/HTML document.

### Chat

**Q: Why does the chat say "no relevant information found"?**
A: This means the vector search didn't find document chunks matching your question. Try:
- Rephrasing your question
- Checking that documents are in READY status
- Ensuring the topic is covered in the ingested filings

**Q: Why does the chat refuse to answer my question?**
A: The AI is designed to only answer questions about SEC filings. It will refuse questions about stock price predictions, investment advice, or unrelated topics.

**Q: Can I ask follow-up questions?**
A: Yes! The chat remembers your conversation history within a session. You can ask follow-ups like "Can you elaborate on the second risk factor?" and the AI will understand the context.

### Analysis

**Q: What does "No Data" mean for a criterion?**
A: It means the company's financial data doesn't include the fields needed for that formula. For example, a company that doesn't report inventory won't have an inventory turnover ratio. This criterion is excluded from scoring and doesn't affect the grade.

**Q: Can I change the thresholds?**
A: Yes! Create a custom analysis profile or edit an existing one. You can adjust thresholds, weights, and lookback periods for every criterion.

**Q: Why does my analysis show no results?**
A: Make sure the company has financial data available (check the Financials tab). Financial data is extracted from XBRL during document ingestion. If documents are in READY status but the Financials tab is empty, the company's SEC filings may not have standard XBRL data.

**Q: What's the difference between "Run Analysis" and "Compare"?**
A: "Run Analysis" scores a single company (or multiple companies individually). "Compare" scores multiple companies on the same profile and ranks them against each other in a side-by-side table.

### Data & Privacy

**Q: Where is my data stored?**
A: All data is stored in your deployment's PostgreSQL database, Qdrant vector store, and Azure Blob Storage. In local development, all data stays on your machine (via Docker containers).

**Q: Is my data sent to third parties?**
A: Document text is sent to Azure OpenAI for embedding generation and chat responses. No data is shared with any other third parties. Azure OpenAI does not use your data for model training.

**Q: Can I delete all data for a company?**
A: Yes. Deleting a company removes all associated documents, financial data, chat sessions, and analysis results permanently.

---

*For technical documentation and development setup, see the [Developer Guide](./developer-guide.md).*
