# filepath: backend/tests/performance/locustfile.py
"""
Locust performance test suite for InvestorInsights API.

Covers four hot-path categories:
  1. Company CRUD — list, detail, create/update/delete lifecycle
  2. Document ingestion — upload, list, detail
  3. Chat — SSE streaming response (time-to-first-token proxy)
  4. Analysis — run scoring engine, list results, comparison

Usage:
  # Headless smoke run (50 users, 60 s)
  locust -f backend/tests/performance/locustfile.py \
    --headless -u 50 -r 10 --run-time 60s \
    --host http://localhost:8000 \
    --csv backend/tests/performance/results

  # Web UI (interactive)
  locust -f backend/tests/performance/locustfile.py \
    --host http://localhost:8000

Environment variables:
  PERF_API_KEY   — API key for X-API-Key header (default: test-key)
  PERF_HOST      — Base URL (overridden by --host flag)

T802: Performance testing — ingestion, API p95, chat TTFT, analysis benchmarks.
"""

from __future__ import annotations

import json
import os
import random
import string
import time
import uuid

from locust import HttpUser, between, events, tag, task


# ── Configuration ────────────────────────────────────────────────

API_KEY = os.getenv("PERF_API_KEY", "test-key")
API_PREFIX = "/api/v1"

# Headers shared by all authenticated requests
AUTH_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

UPLOAD_HEADERS = {
    "X-API-Key": API_KEY,
    # Content-Type set automatically for multipart
}

# Reusable company tickers for seeding
_TICKERS = [
    "AAPL", "MSFT", "GOOG", "AMZN", "META",
    "TSLA", "NVDA", "JPM", "V", "JNJ",
    "WMT", "PG", "UNH", "HD", "DIS",
]

# Minimal valid PDF (1-page blank) — base64 decoded at module level.
# This is the smallest legal PDF that PyMuPDF can parse.
_MINIMAL_PDF = (
    b"%PDF-1.0\n1 0 obj<</Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


# ── Helpers ──────────────────────────────────────────────────────


def _rand_ticker() -> str:
    """Return a random 4-char uppercase ticker."""
    return "".join(random.choices(string.ascii_uppercase, k=4))


def _rand_uuid() -> str:
    return str(uuid.uuid4())


# ── Custom metrics event listener ────────────────────────────────

_p95_thresholds: dict[str, int] = {
    # name → max p95 ms
    "GET /companies": 200,
    "GET /companies/{id}": 150,
    "POST /companies": 300,
    "GET /documents": 200,
    "POST /analysis/run": 2000,
    "GET /analysis/results": 300,
    "POST /analysis/compare": 3000,
    "GET /health": 500,
}


@events.quitting.add_listener
def _check_p95(environment, **_kwargs):
    """Fail the run if any p95 exceeds the budget (CI gate)."""
    failures = []
    for stat in environment.runner.stats.entries.values():
        threshold = _p95_thresholds.get(stat.name)
        if threshold is not None and stat.num_requests > 0:
            p95 = stat.get_response_time_percentile(0.95) or 0
            if p95 > threshold:
                failures.append(
                    f"  {stat.name}: p95={p95:.0f}ms > budget={threshold}ms"
                )
    if failures:
        msg = "P95 budget exceeded:\n" + "\n".join(failures)
        environment.process_exit_code = 1
        print(f"\n❌ PERFORMANCE GATE FAILED\n{msg}\n")
    else:
        print("\n✅ All p95 budgets within threshold.\n")


# =====================================================================
# User classes
# =====================================================================


class CompanyUser(HttpUser):
    """Simulates a user performing Company CRUD operations.

    Weight: 40 % of total load — companies list/detail is the most
    common read path (dashboard, detail pages, search).
    """

    weight = 4
    wait_time = between(0.5, 2.0)

    # Shared state for created company ids (per-user instance)
    _company_ids: list[str]
    _created_ids: list[str]

    def on_start(self):
        self._company_ids = []
        self._created_ids = []
        # Seed: create 2 companies so reads have data
        for _ in range(2):
            cid = self._create_company()
            if cid:
                self._company_ids.append(cid)

    def on_stop(self):
        # Cleanup: delete companies we created
        for cid in self._created_ids:
            self.client.delete(
                f"{API_PREFIX}/companies/{cid}?confirm=true",
                headers=AUTH_HEADERS,
                name="DELETE /companies/{id}",
            )

    def _create_company(self) -> str | None:
        ticker = _rand_ticker()
        resp = self.client.post(
            f"{API_PREFIX}/companies",
            json={
                "ticker": ticker,
                "name": f"PerfTest {ticker} Inc.",
                "sector": "Technology",
            },
            headers=AUTH_HEADERS,
            name="POST /companies",
        )
        if resp.status_code == 201:
            cid = resp.json().get("id")
            if cid:
                self._created_ids.append(cid)
            return cid
        return None

    @tag("company", "read")
    @task(5)
    def list_companies(self):
        """GET /companies — paginated list (dashboard hot path)."""
        self.client.get(
            f"{API_PREFIX}/companies?limit=20&offset=0",
            headers=AUTH_HEADERS,
            name="GET /companies",
        )

    @tag("company", "read")
    @task(3)
    def get_company_detail(self):
        """GET /companies/{id} — single company detail."""
        if not self._company_ids:
            return
        cid = random.choice(self._company_ids)
        self.client.get(
            f"{API_PREFIX}/companies/{cid}",
            headers=AUTH_HEADERS,
            name="GET /companies/{id}",
        )

    @tag("company", "read")
    @task(2)
    def search_companies(self):
        """GET /companies?search= — search by ticker/name."""
        query = random.choice(_TICKERS)
        self.client.get(
            f"{API_PREFIX}/companies?search={query}&limit=10",
            headers=AUTH_HEADERS,
            name="GET /companies?search",
        )

    @tag("company", "write")
    @task(1)
    def create_and_update_company(self):
        """POST + PUT + DELETE lifecycle."""
        cid = self._create_company()
        if not cid:
            return

        # Update
        self.client.put(
            f"{API_PREFIX}/companies/{cid}",
            json={"description": "Updated by perf test"},
            headers=AUTH_HEADERS,
            name="PUT /companies/{id}",
        )

        # Delete
        self.client.delete(
            f"{API_PREFIX}/companies/{cid}?confirm=true",
            headers=AUTH_HEADERS,
            name="DELETE /companies/{id}",
        )
        # Remove from created_ids (already deleted)
        if cid in self._created_ids:
            self._created_ids.remove(cid)


class DocumentUser(HttpUser):
    """Simulates document upload and listing.

    Weight: 20 % — ingestion is less frequent but latency-sensitive.
    """

    weight = 2
    wait_time = between(1.0, 3.0)

    _company_id: str | None = None
    _doc_ids: list[str]

    def on_start(self):
        self._doc_ids = []
        # Create a company for document operations
        resp = self.client.post(
            f"{API_PREFIX}/companies",
            json={
                "ticker": _rand_ticker(),
                "name": "DocPerfTest Inc.",
                "sector": "Finance",
            },
            headers=AUTH_HEADERS,
            name="POST /companies",
        )
        if resp.status_code == 201:
            self._company_id = resp.json().get("id")

    def on_stop(self):
        if self._company_id:
            self.client.delete(
                f"{API_PREFIX}/companies/{self._company_id}?confirm=true",
                headers=AUTH_HEADERS,
                name="DELETE /companies/{id}",
            )

    @tag("document", "write")
    @task(2)
    def upload_document(self):
        """POST /companies/{id}/documents — upload a minimal PDF."""
        if not self._company_id:
            return
        year = random.randint(2018, 2025)
        resp = self.client.post(
            f"{API_PREFIX}/companies/{self._company_id}/documents",
            files={"file": ("test.pdf", _MINIMAL_PDF, "application/pdf")},
            data={
                "doc_type": "10-K",
                "fiscal_year": str(year),
                "filing_date": f"{year}-03-01",
                "period_end_date": f"{year}-12-31",
            },
            headers=UPLOAD_HEADERS,
            name="POST /documents (upload)",
        )
        if resp.status_code in (200, 201, 202):
            doc_id = resp.json().get("id")
            if doc_id:
                self._doc_ids.append(doc_id)

    @tag("document", "read")
    @task(5)
    def list_documents(self):
        """GET /companies/{id}/documents — list docs for a company."""
        if not self._company_id:
            return
        self.client.get(
            f"{API_PREFIX}/companies/{self._company_id}/documents?limit=20",
            headers=AUTH_HEADERS,
            name="GET /documents",
        )

    @tag("document", "read")
    @task(3)
    def get_document_detail(self):
        """GET /companies/{id}/documents/{doc_id} — document detail."""
        if not self._company_id or not self._doc_ids:
            return
        doc_id = random.choice(self._doc_ids)
        self.client.get(
            f"{API_PREFIX}/companies/{self._company_id}/documents/{doc_id}",
            headers=AUTH_HEADERS,
            name="GET /documents/{id}",
        )


class ChatUser(HttpUser):
    """Simulates chat interactions — measures time-to-first-token (TTFT).

    Weight: 15 % — chat is high-latency but critical user experience.
    TTFT is measured as the time from request start to the first SSE
    data chunk arriving.
    """

    weight = 2
    wait_time = between(2.0, 5.0)

    _company_id: str | None = None

    def on_start(self):
        resp = self.client.post(
            f"{API_PREFIX}/companies",
            json={
                "ticker": _rand_ticker(),
                "name": "ChatPerfTest Inc.",
                "sector": "Healthcare",
            },
            headers=AUTH_HEADERS,
            name="POST /companies",
        )
        if resp.status_code == 201:
            self._company_id = resp.json().get("id")

    def on_stop(self):
        if self._company_id:
            self.client.delete(
                f"{API_PREFIX}/companies/{self._company_id}?confirm=true",
                headers=AUTH_HEADERS,
                name="DELETE /companies/{id}",
            )

    @tag("chat")
    @task(1)
    def chat_stream(self):
        """POST /companies/{id}/chat — SSE streaming chat.

        Measures TTFT (time-to-first-token) as a custom metric.
        We read the stream until the first SSE data line, then close.
        """
        if not self._company_id:
            return

        questions = [
            "What is the company's revenue growth?",
            "Summarize the risk factors.",
            "What are the key financial highlights?",
            "How does the company compare to peers?",
            "What is the debt-to-equity ratio trend?",
        ]

        start = time.perf_counter()
        ttft = None

        with self.client.post(
            f"{API_PREFIX}/companies/{self._company_id}/chat",
            json={
                "message": random.choice(questions),
            },
            headers=AUTH_HEADERS,
            name="POST /chat (SSE)",
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Chat returned {resp.status_code}")
                return

            try:
                for line in resp.iter_lines():
                    if line and line.startswith("data:"):
                        ttft = (time.perf_counter() - start) * 1000  # ms
                        break
            except Exception as exc:
                resp.failure(f"Stream error: {exc}")
                return

            if ttft is not None:
                # Fire custom TTFT metric
                events.request.fire(
                    request_type="CUSTOM",
                    name="Chat TTFT",
                    response_time=ttft,
                    response_length=0,
                    exception=None,
                    context={},
                )
                resp.success()
            else:
                resp.failure("No SSE data received")

    @tag("chat", "read")
    @task(2)
    def list_chat_sessions(self):
        """GET /companies/{id}/chat/sessions — list sessions."""
        if not self._company_id:
            return
        self.client.get(
            f"{API_PREFIX}/companies/{self._company_id}/chat/sessions?limit=10",
            headers=AUTH_HEADERS,
            name="GET /chat/sessions",
        )


class AnalysisUser(HttpUser):
    """Simulates analysis operations — run, results, compare.

    Weight: 25 % — analysis is computationally expensive, key to
    validate p95 budgets for scoring engine.
    """

    weight = 3
    wait_time = between(1.0, 4.0)

    _company_ids: list[str]
    _profile_id: str | None = None
    _result_ids: list[str]

    def on_start(self):
        self._company_ids = []
        self._result_ids = []

        # Create 3 companies for comparison
        for _ in range(3):
            resp = self.client.post(
                f"{API_PREFIX}/companies",
                json={
                    "ticker": _rand_ticker(),
                    "name": f"AnalysisPerfTest {_rand_ticker()} Inc.",
                    "sector": "Technology",
                },
                headers=AUTH_HEADERS,
                name="POST /companies",
            )
            if resp.status_code == 201:
                self._company_ids.append(resp.json()["id"])

        # Create or find a profile
        resp = self.client.get(
            f"{API_PREFIX}/analysis/profiles?limit=1",
            headers=AUTH_HEADERS,
            name="GET /analysis/profiles",
        )
        if resp.status_code == 200:
            profiles = resp.json().get("items", [])
            if profiles:
                self._profile_id = profiles[0]["id"]

        if not self._profile_id:
            # Create a minimal profile
            resp = self.client.post(
                f"{API_PREFIX}/analysis/profiles",
                json={
                    "name": f"PerfProfile-{_rand_ticker()}",
                    "description": "Performance test profile",
                    "criteria": [
                        {
                            "name": "ROE Check",
                            "category": "profitability",
                            "formula": "return_on_equity",
                            "comparison": ">",
                            "threshold_value": 0.1,
                            "weight": 1.0,
                        },
                        {
                            "name": "Current Ratio",
                            "category": "liquidity",
                            "formula": "current_ratio",
                            "comparison": ">",
                            "threshold_value": 1.0,
                            "weight": 1.0,
                        },
                    ],
                },
                headers=AUTH_HEADERS,
                name="POST /analysis/profiles",
            )
            if resp.status_code == 201:
                self._profile_id = resp.json()["id"]

    def on_stop(self):
        for cid in self._company_ids:
            self.client.delete(
                f"{API_PREFIX}/companies/{cid}?confirm=true",
                headers=AUTH_HEADERS,
                name="DELETE /companies/{id}",
            )

    @tag("analysis", "write")
    @task(3)
    def run_analysis(self):
        """POST /analysis/run — execute scoring engine."""
        if not self._company_ids or not self._profile_id:
            return
        cid = random.choice(self._company_ids)
        resp = self.client.post(
            f"{API_PREFIX}/analysis/run",
            json={
                "company_ids": [cid],
                "profile_id": self._profile_id,
            },
            headers=AUTH_HEADERS,
            name="POST /analysis/run",
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for r in results:
                rid = r.get("id")
                if rid:
                    self._result_ids.append(rid)

    @tag("analysis", "read")
    @task(4)
    def list_results(self):
        """GET /analysis/results — list past results."""
        self.client.get(
            f"{API_PREFIX}/analysis/results?limit=20",
            headers=AUTH_HEADERS,
            name="GET /analysis/results",
        )

    @tag("analysis", "read")
    @task(2)
    def get_result_detail(self):
        """GET /analysis/results/{id} — result detail."""
        if not self._result_ids:
            return
        rid = random.choice(self._result_ids)
        self.client.get(
            f"{API_PREFIX}/analysis/results/{rid}",
            headers=AUTH_HEADERS,
            name="GET /analysis/results/{id}",
        )

    @tag("analysis", "write")
    @task(1)
    def compare_companies(self):
        """POST /analysis/compare — multi-company comparison."""
        if len(self._company_ids) < 2 or not self._profile_id:
            return
        self.client.post(
            f"{API_PREFIX}/analysis/compare",
            json={
                "company_ids": self._company_ids[:3],
                "profile_id": self._profile_id,
                "generate_summary": False,
            },
            headers=AUTH_HEADERS,
            name="POST /analysis/compare",
        )

    @tag("analysis", "read")
    @task(2)
    def list_formulas(self):
        """GET /analysis/formulas — list built-in formulas."""
        self.client.get(
            f"{API_PREFIX}/analysis/formulas",
            headers=AUTH_HEADERS,
            name="GET /analysis/formulas",
        )


class HealthUser(HttpUser):
    """Lightweight health-check poller (simulates monitoring agent).

    Weight: 5 % — minimal load, validates infrastructure probes.
    """

    weight = 1
    wait_time = between(5.0, 10.0)

    @tag("health")
    @task(1)
    def health_check(self):
        """GET /health — no auth required."""
        self.client.get(
            f"{API_PREFIX}/health",
            name="GET /health",
        )
