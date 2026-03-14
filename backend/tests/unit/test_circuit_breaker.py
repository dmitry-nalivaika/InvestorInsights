# filepath: backend/tests/unit/test_circuit_breaker.py
"""Unit tests for the circuit breaker implementation.

Covers:
- State machine transitions (closed -> open -> half_open -> closed)
- Failure counting and threshold tripping
- Recovery timeout and automatic half-open transition
- Async context manager usage
- Decorator usage
- Excluded exceptions
- Pre-configured breakers (azure_openai, sec_edgar, qdrant)
- Registry functions (get, register, reset_all, get_all)
- CircuitOpenError attributes
- Edge cases (reset, repr, retry_after)
"""

from __future__ import annotations

import os
import time

# Set required env var before any app imports
os.environ.setdefault("API_KEY", "test-circuit-breaker")

import pytest

from app.clients.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    _breakers,
    get_all_circuit_breakers,
    get_circuit_breaker,
    register_circuit_breaker,
    reset_all_circuit_breakers,
)

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture(autouse=True)
def _clean_breakers():
    """Reset the global breaker registry before each test."""
    saved = dict(_breakers)
    _breakers.clear()
    yield
    _breakers.clear()
    _breakers.update(saved)


@pytest.fixture()
def breaker() -> CircuitBreaker:
    """A fresh circuit breaker with low thresholds for fast testing."""
    return CircuitBreaker(
        "test_service",
        failure_threshold=3,
        recovery_timeout=0.1,  # 100ms for fast tests
    )


# =====================================================================
# State machine basics
# =====================================================================


class TestCircuitBreakerStates:
    """Test the circuit breaker state transitions."""

    def test_initial_state_is_closed(self, breaker: CircuitBreaker) -> None:
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.total_trips == 0

    def test_success_keeps_closed(self, breaker: CircuitBreaker) -> None:
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_failure_below_threshold_stays_closed(
        self, breaker: CircuitBreaker
    ) -> None:
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 2

    def test_failure_at_threshold_opens_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.total_trips == 1

    def test_open_rejects_calls(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        with pytest.raises(CircuitOpenError) as exc_info:
            breaker._check_state()
        assert exc_info.value.service == "test_service"
        assert exc_info.value.retry_after >= 0

    def test_open_transitions_to_half_open_after_timeout(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        # Wait for recovery timeout (100ms)
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_half_open_failure_reopens_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN
        breaker.record_failure()
        assert breaker._state == CircuitState.OPEN
        assert breaker.total_trips == 2  # Tripped twice

    def test_manual_reset(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_success_resets_failure_count(
        self, breaker: CircuitBreaker
    ) -> None:
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        breaker.record_success()
        assert breaker.failure_count == 0


# =====================================================================
# retry_after property
# =====================================================================


class TestRetryAfter:
    def test_retry_after_zero_when_closed(
        self, breaker: CircuitBreaker
    ) -> None:
        assert breaker.retry_after == 0.0

    def test_retry_after_positive_when_open(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        assert breaker.retry_after > 0
        assert breaker.retry_after <= breaker.recovery_timeout

    def test_retry_after_decreases_over_time(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        first = breaker.retry_after
        time.sleep(0.05)
        second = breaker.retry_after
        assert second < first


# =====================================================================
# Async context manager
# =====================================================================


class TestAsyncContextManager:
    @pytest.mark.asyncio()
    async def test_context_manager_success(
        self, breaker: CircuitBreaker
    ) -> None:
        async with breaker:
            pass  # Simulate successful call
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio()
    async def test_context_manager_failure(
        self, breaker: CircuitBreaker
    ) -> None:
        with pytest.raises(RuntimeError):
            async with breaker:
                raise RuntimeError("boom")
        assert breaker.failure_count == 1

    @pytest.mark.asyncio()
    async def test_context_manager_trips_after_threshold(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            with pytest.raises(RuntimeError):
                async with breaker:
                    raise RuntimeError("boom")
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio()
    async def test_context_manager_rejects_when_open(
        self, breaker: CircuitBreaker
    ) -> None:
        for _ in range(3):
            breaker.record_failure()
        with pytest.raises(CircuitOpenError):
            async with breaker:
                pass  # Should never reach here

    @pytest.mark.asyncio()
    async def test_context_manager_excluded_exception(self) -> None:
        cb = CircuitBreaker(
            "test_excluded",
            failure_threshold=2,
            recovery_timeout=1.0,
            excluded_exceptions=(ValueError,),
        )
        # ValueError should not count as a failure
        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("client error")
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio()
    async def test_context_manager_non_excluded_exception_counts(self) -> None:
        cb = CircuitBreaker(
            "test_excluded2",
            failure_threshold=2,
            recovery_timeout=1.0,
            excluded_exceptions=(ValueError,),
        )
        # RuntimeError IS counted as a failure
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("service error")
        assert cb.failure_count == 1


# =====================================================================
# Decorator
# =====================================================================


class TestProtectDecorator:
    @pytest.mark.asyncio()
    async def test_decorator_success(self, breaker: CircuitBreaker) -> None:
        @breaker.protect
        async def ok_call() -> str:
            return "ok"

        result = await ok_call()
        assert result == "ok"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio()
    async def test_decorator_failure(self, breaker: CircuitBreaker) -> None:
        @breaker.protect
        async def bad_call() -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await bad_call()
        assert breaker.failure_count == 1

    @pytest.mark.asyncio()
    async def test_decorator_trips_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        @breaker.protect
        async def bad_call() -> str:
            raise RuntimeError("boom")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await bad_call()
        assert breaker.state == CircuitState.OPEN

        # Next call should get CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await bad_call()

    @pytest.mark.asyncio()
    async def test_decorator_preserves_function_metadata(
        self, breaker: CircuitBreaker
    ) -> None:
        @breaker.protect
        async def my_function() -> str:
            """My docstring."""
            return "ok"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


# =====================================================================
# CircuitOpenError
# =====================================================================


class TestCircuitOpenError:
    def test_error_attributes(self) -> None:
        err = CircuitOpenError("my_service", 42.5)
        assert err.service == "my_service"
        assert err.retry_after == 42.5
        assert "my_service" in str(err)
        assert "42.5" in str(err)

    def test_error_is_exception(self) -> None:
        err = CircuitOpenError("svc", 1.0)
        assert isinstance(err, Exception)


# =====================================================================
# Pre-configured breakers (plan.md spec)
# =====================================================================


class TestPreConfiguredBreakers:
    def test_azure_openai_breaker(self) -> None:
        cb = get_circuit_breaker("azure_openai")
        assert cb.service == "azure_openai"
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0

    def test_sec_edgar_breaker(self) -> None:
        cb = get_circuit_breaker("sec_edgar")
        assert cb.service == "sec_edgar"
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 300.0

    def test_qdrant_breaker(self) -> None:
        cb = get_circuit_breaker("qdrant")
        assert cb.service == "qdrant"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0

    def test_unknown_service_raises_key_error(self) -> None:
        # Ensure defaults are initialised first
        get_circuit_breaker("azure_openai")
        with pytest.raises(KeyError, match="no_such_service"):
            get_circuit_breaker("no_such_service")


# =====================================================================
# Registry functions
# =====================================================================


class TestRegistryFunctions:
    def test_get_all_circuit_breakers(self) -> None:
        breakers = get_all_circuit_breakers()
        assert "azure_openai" in breakers
        assert "sec_edgar" in breakers
        assert "qdrant" in breakers
        assert len(breakers) == 3

    def test_get_all_returns_copy(self) -> None:
        breakers = get_all_circuit_breakers()
        breakers["new_service"] = CircuitBreaker("new_service")
        # Original registry should not be affected
        assert "new_service" not in _breakers

    def test_register_custom_breaker(self) -> None:
        cb = register_circuit_breaker(
            "custom_service",
            failure_threshold=7,
            recovery_timeout=120.0,
        )
        assert cb.service == "custom_service"
        assert cb.failure_threshold == 7
        assert cb.recovery_timeout == 120.0
        # Should be retrievable
        assert get_circuit_breaker("custom_service") is cb

    def test_register_overwrites_existing(self) -> None:
        original = get_circuit_breaker("azure_openai")
        new = register_circuit_breaker(
            "azure_openai",
            failure_threshold=99,
            recovery_timeout=999.0,
        )
        assert new is not original
        assert get_circuit_breaker("azure_openai") is new
        assert new.failure_threshold == 99

    def test_reset_all_circuit_breakers(self) -> None:
        # Trip all breakers
        for name in ("azure_openai", "sec_edgar", "qdrant"):
            cb = get_circuit_breaker(name)
            for _ in range(cb.failure_threshold):
                cb.record_failure()
            assert cb.state == CircuitState.OPEN

        reset_all_circuit_breakers()

        for name in ("azure_openai", "sec_edgar", "qdrant"):
            cb = get_circuit_breaker(name)
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0


# =====================================================================
# Repr
# =====================================================================


class TestRepr:
    def test_repr_closed(self, breaker: CircuitBreaker) -> None:
        r = repr(breaker)
        assert "test_service" in r
        assert "closed" in r
        assert "0/3" in r

    def test_repr_open(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            breaker.record_failure()
        r = repr(breaker)
        assert "open" in r
