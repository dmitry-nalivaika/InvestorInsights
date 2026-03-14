# filepath: backend/tests/performance/README.md
# Performance Testing — InvestorInsights

## Overview

Load/stress tests for the InvestorInsights API using [Locust](https://locust.io/).
Tests cover the four hot-path categories with p95 latency budgets.

## Quick Start

```bash
# 1. Start the backend (with DB, Redis, Qdrant running)
cd backend && uvicorn app.main:app --reload

# 2. Headless smoke run (CI-compatible)
locust -f backend/tests/performance/locustfile.py \
  --headless -u 50 -r 10 --run-time 60s \
  --host http://localhost:8000 \
  --csv backend/tests/performance/results

# 3. Interactive Web UI
locust -f backend/tests/performance/locustfile.py \
  --host http://localhost:8000
# Open http://localhost:8089
```

## User Classes & Weights

| Class          | Weight | Simulates                          |
| -------------- | ------ | ---------------------------------- |
| CompanyUser    | 40 %   | Dashboard browsing, CRUD           |
| AnalysisUser   | 25 %   | Scoring runs, result reads, compare|
| DocumentUser   | 20 %   | Upload, list, detail               |
| ChatUser       | 15 %   | SSE streaming, session listing     |
| HealthUser     |  5 %   | Monitoring agent polling           |

## P95 Latency Budgets

| Endpoint              | Budget (ms) |
| --------------------- | ----------- |
| GET /companies        | 200         |
| GET /companies/{id}   | 150         |
| POST /companies       | 300         |
| GET /documents        | 200         |
| POST /analysis/run    | 2 000       |
| GET /analysis/results | 300         |
| POST /analysis/compare| 3 000       |
| GET /health           | 500         |

The headless run exits with code 1 if any p95 exceeds its budget
(via the `_check_p95` event listener).

## Custom Metrics

- **Chat TTFT** — Time-to-first-token for SSE streaming chat responses,
  fired as a `CUSTOM` request type in Locust stats.

## Environment Variables

| Variable      | Default    | Description             |
| ------------- | ---------- | ----------------------- |
| `PERF_API_KEY`| `test-key` | API key for auth header |
| `PERF_HOST`   | —          | Override base URL       |

## CSV Output

When run with `--csv`, Locust writes three CSV files:
- `results_stats.csv` — aggregate statistics
- `results_stats_history.csv` — time-series data
- `results_failures.csv` — failure details

These can be committed to track regressions or parsed in CI.
