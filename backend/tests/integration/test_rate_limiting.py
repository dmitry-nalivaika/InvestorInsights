# filepath: backend/tests/integration/test_rate_limiting.py
"""
Integration tests for rate-limiting middleware (T800a).

Tests verify:
  - CRUD endpoints enforce 100 req/min (configurable)
  - Chat endpoints enforce 20 req/min (configurable)
  - 429 responses include proper headers
  - Health endpoint is exempt from rate limiting
  - Rate limiter fails open when Redis is unavailable
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

# Set env vars before any app imports
os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

from app.api.middleware.rate_limiter import RateLimitMiddleware
from app.config import get_settings

# ── Helpers ──────────────────────────────────────────────────────


def _create_test_app(crud_limit: int = 5, chat_limit: int = 2) -> FastAPI:
    """Create a minimal FastAPI app with rate limiting for tests.

    Uses low limits so we don't need hundreds of requests.
    """
    settings = get_settings()
    # Override limits for testing
    settings.api_rate_limit_crud = crud_limit
    settings.api_rate_limit_chat = chat_limit

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings)

    # Minimal API routes
    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.get("/companies")
    async def list_companies():
        return {"items": []}

    @router.post("/companies/{company_id}/chat")
    async def chat(company_id: str):
        return {"message": "ok"}

    app.include_router(router)
    return app


# ── Mock Redis ───────────────────────────────────────────────────

_counter: dict[str, int] = {}


def _make_mock_redis(limits: dict[str, int] | None = None):
    """Create a mock Redis client that tracks call counts in-memory."""
    _counter.clear()

    async def mock_check_rate_limit(
        key: str,
        max_requests: int,
        window_seconds: int,
        *,
        namespace: str = "ratelimit",
    ) -> tuple[bool, int]:
        full_key = f"{namespace}:{key}"
        _counter[full_key] = _counter.get(full_key, 0) + 1
        current = _counter[full_key]
        remaining = max(0, max_requests - current)
        return (current <= max_requests, remaining)

    mock = AsyncMock()
    mock.check_rate_limit = mock_check_rate_limit
    return mock


# ── Tests ────────────────────────────────────────────────────────


class TestCrudRateLimiting:
    """CRUD endpoints enforce api_rate_limit_crud."""

    def setup_method(self):
        _counter.clear()
        self.app = _create_test_app(crud_limit=5, chat_limit=2)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_allows_requests_within_limit(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            for i in range(5):
                resp = self.client.get("/api/v1/companies")
                assert resp.status_code == 200, f"Request {i+1} should succeed"

    def test_blocks_requests_over_limit(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            # Exhaust the limit
            for _ in range(5):
                self.client.get("/api/v1/companies")

            # 6th request should be 429
            resp = self.client.get("/api/v1/companies")
            assert resp.status_code == 429

    def test_429_response_has_correct_headers(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            for _ in range(5):
                self.client.get("/api/v1/companies")

            resp = self.client.get("/api/v1/companies")
            assert resp.status_code == 429
            assert resp.headers["X-RateLimit-Limit"] == "5"
            assert resp.headers["X-RateLimit-Remaining"] == "0"
            assert resp.headers["Retry-After"] == "60"
            assert resp.headers["X-RateLimit-Reset"] == "60"

    def test_429_response_body(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            for _ in range(5):
                self.client.get("/api/v1/companies")

            resp = self.client.get("/api/v1/companies")
            body = resp.json()
            assert "detail" in body
            assert "rate limit" in body["detail"].lower()

    def test_success_responses_include_rate_limit_headers(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            resp = self.client.get("/api/v1/companies")
            assert resp.status_code == 200
            assert "X-RateLimit-Limit" in resp.headers
            assert "X-RateLimit-Remaining" in resp.headers
            assert "X-RateLimit-Reset" in resp.headers


class TestChatRateLimiting:
    """Chat endpoints enforce the lower api_rate_limit_chat."""

    def setup_method(self):
        _counter.clear()
        self.app = _create_test_app(crud_limit=100, chat_limit=2)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_chat_enforces_separate_limit(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            # 2 chat requests should succeed
            for i in range(2):
                resp = self.client.post("/api/v1/companies/abc/chat")
                assert resp.status_code == 200, f"Chat request {i+1} should succeed"

            # 3rd should be blocked
            resp = self.client.post("/api/v1/companies/abc/chat")
            assert resp.status_code == 429

    def test_chat_limit_header_shows_chat_limit(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            resp = self.client.post("/api/v1/companies/abc/chat")
            assert resp.headers["X-RateLimit-Limit"] == "2"

    def test_crud_and_chat_use_separate_buckets(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            # Exhaust chat limit
            for _ in range(2):
                self.client.post("/api/v1/companies/abc/chat")

            # CRUD should still work
            resp = self.client.get("/api/v1/companies")
            assert resp.status_code == 200


class TestRateLimitExemptions:
    """Health endpoint and OPTIONS are exempt."""

    def setup_method(self):
        _counter.clear()
        self.app = _create_test_app(crud_limit=2, chat_limit=1)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_health_endpoint_is_exempt(self):
        mock_redis = _make_mock_redis()
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            # Even with very low limits, health always works
            for _ in range(10):
                resp = self.client.get("/api/v1/health")
                assert resp.status_code == 200


class TestRateLimitRedisUnavailable:
    """When Redis is down, rate limiter fails open."""

    def setup_method(self):
        _counter.clear()
        self.app = _create_test_app(crud_limit=1, chat_limit=1)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_fails_open_when_redis_not_initialised(self):
        """Requests succeed when Redis is not available (RuntimeError)."""
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            side_effect=RuntimeError("Redis not initialised"),
        ):
            for _ in range(5):
                resp = self.client.get("/api/v1/companies")
                assert resp.status_code == 200

    def test_fails_open_on_redis_connection_error(self):
        """Requests succeed when Redis raises a connection error."""
        mock_redis = AsyncMock()
        mock_redis.check_rate_limit = AsyncMock(
            side_effect=ConnectionError("Redis connection lost")
        )
        with patch(
            "app.api.middleware.rate_limiter.get_redis_client",
            return_value=mock_redis,
        ):
            for _ in range(5):
                resp = self.client.get("/api/v1/companies")
                assert resp.status_code == 200
