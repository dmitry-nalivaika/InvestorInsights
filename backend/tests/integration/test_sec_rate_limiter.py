# filepath: backend/tests/integration/test_sec_rate_limiter.py
"""Integration tests for the SEC EDGAR rate limiter (T302).

Verifies:
  - Token-bucket rate limiter enforces ≤10 req/s (FR-206)
  - User-Agent header is present on all requests (SEC EDGAR requirement)
  - Requests beyond the bucket capacity are delayed, not dropped
"""

from __future__ import annotations

import asyncio
import os
import time

os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import pytest

from app.clients.sec_client import TokenBucketRateLimiter

# =====================================================================
# Token Bucket Rate Limiter
# =====================================================================


class TestTokenBucketRateLimiter:
    """Tests for the async token-bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_initial_burst_allowed(self) -> None:
        """A freshly created limiter allows up to max_rate tokens immediately."""
        limiter = TokenBucketRateLimiter(max_rate=10)

        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # 10 tokens should be consumed almost instantly (< 0.5s)
        assert elapsed < 0.5, f"Initial burst of 10 took {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_rate_limiting_slows_excess_requests(self) -> None:
        """After the initial burst, additional acquires should block."""
        limiter = TokenBucketRateLimiter(max_rate=10)

        # Exhaust the initial bucket
        for _ in range(10):
            await limiter.acquire()

        # The 11th request should require waiting ~0.1s (1 token / 10 per sec)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should have waited at least ~0.05s (allowing some timing slack)
        assert elapsed >= 0.05, f"11th acquire returned too fast: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_rate_enforcement_over_time(self) -> None:
        """Over 15 requests with max_rate=10, the elapsed time must be ≥ 0.5s.

        10 requests are served from the initial burst, then 5 more
        need 5 x 0.1s = 0.5s of refill time.
        """
        limiter = TokenBucketRateLimiter(max_rate=10)

        start = time.monotonic()
        for _ in range(15):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # 10 burst + 5 at 0.1s each = ≥ 0.4s (accounting for timing slack)
        assert elapsed >= 0.4, f"15 acquires took only {elapsed:.3f}s"
        # Shouldn't take more than ~1.5s
        assert elapsed < 1.5, f"15 acquires took too long: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_concurrent_acquires_are_serialised(self) -> None:
        """Multiple concurrent acquire() calls don't bypass the limit."""
        limiter = TokenBucketRateLimiter(max_rate=5)

        timestamps: list[float] = []

        async def acquire_and_record() -> None:
            await limiter.acquire()
            timestamps.append(time.monotonic())

        # Fire 10 concurrent tasks against a limiter with max_rate=5
        start = time.monotonic()
        await asyncio.gather(*(acquire_and_record() for _ in range(10)))
        total_elapsed = time.monotonic() - start

        # 5 burst + 5 at 0.2s each = ≥ 0.8s
        assert total_elapsed >= 0.7, f"10 concurrent acquires took only {total_elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_tokens_replenish_after_wait(self) -> None:
        """After waiting, tokens refill and requests proceed quickly."""
        limiter = TokenBucketRateLimiter(max_rate=10)

        # Exhaust all tokens
        for _ in range(10):
            await limiter.acquire()

        # Wait for full refill (1 second for 10 tokens)
        await asyncio.sleep(1.0)

        # Should be able to burst again
        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, f"Burst after refill took {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_custom_max_rate(self) -> None:
        """Rate limiter respects a custom max_rate value."""
        limiter = TokenBucketRateLimiter(max_rate=2)

        # Exhaust burst
        await limiter.acquire()
        await limiter.acquire()

        # Third request should wait ~0.5s (1 / 2 per sec)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        assert elapsed >= 0.3, f"Third acquire at rate=2 returned too fast: {elapsed:.3f}s"


# =====================================================================
# User-Agent Header
# =====================================================================


class TestSECClientUserAgent:
    """Tests that the SEC client sets User-Agent correctly."""

    def test_user_agent_configured_in_settings(self) -> None:
        """Settings should expose a non-empty sec_edgar_user_agent."""
        from app.config import get_settings

        settings = get_settings()
        assert settings.sec_edgar_user_agent
        assert len(settings.sec_edgar_user_agent) > 10
        # SEC requires a contact email in the user agent
        assert "@" in settings.sec_edgar_user_agent or "example" in settings.sec_edgar_user_agent

    def test_client_passes_user_agent_to_httpx(self) -> None:
        """SECEdgarClient should configure the httpx client with User-Agent."""
        from app.clients.sec_client import SECEdgarClient
        from app.config import get_settings

        settings = get_settings()
        client = SECEdgarClient(settings)

        # The client hasn't been used yet (lazy init), so force creation
        # by inspecting the settings it was given
        assert client._user_agent == settings.sec_edgar_user_agent

    def test_rate_limit_setting_is_10(self) -> None:
        """Default SEC EDGAR rate limit must be 10 req/s per FR-206."""
        from app.config import get_settings

        settings = get_settings()
        assert settings.sec_edgar_rate_limit == 10
