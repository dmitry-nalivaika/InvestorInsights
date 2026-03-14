# filepath: backend/app/clients/circuit_breaker.py
"""
Circuit breaker implementation for external service resilience.

Implements the standard closed → open → half-open state machine
to prevent cascading failures when external services are down.

Circuit breaker configuration (from plan.md):

| Service      | Failure Threshold | Recovery Timeout | Fallback                                |
|--------------|-------------------|------------------|-----------------------------------------|
| Azure OpenAI | 5 consecutive     | 60 s             | Direct OpenAI (if configured)           |
| SEC EDGAR    | 10 consecutive    | 300 s            | Queue for later; existing docs unaffected|
| Qdrant       | 3 consecutive     | 30 s             | Chat unavailable; CRUD still works      |

NFR-400: External service failures MUST NOT crash the application.
NFR-401: When Azure OpenAI is unavailable, CRUD + analysis still function.
NFR-402: When Qdrant is unavailable, CRUD + financial analysis still function.

Usage::

    from app.clients.circuit_breaker import get_circuit_breaker, CircuitOpenError

    cb = get_circuit_breaker("azure_openai")

    async def call_llm():
        async with cb:
            return await openai_client.chat(...)

    # Or use the decorator:
    @cb.protect
    async def call_llm():
        return await openai_client.chat(...)
"""

from __future__ import annotations

import enum
import functools
import time
from typing import TYPE_CHECKING, Any

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)


# =====================================================================
# Circuit states
# =====================================================================


class CircuitState(enum.Enum):
    """Three states of a circuit breaker."""

    CLOSED = "closed"  # Normal operation — calls pass through
    OPEN = "open"  # Circuit tripped — calls rejected immediately
    HALF_OPEN = "half_open"  # Probing — one test call allowed


# =====================================================================
# Exceptions
# =====================================================================


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open.

    Attributes:
        service: The name of the service whose circuit is open.
        retry_after: Seconds until the circuit transitions to half-open.
    """

    def __init__(self, service: str, retry_after: float) -> None:
        self.service = service
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for {service!r} — "
            f"retry after {retry_after:.1f}s"
        )


# =====================================================================
# Circuit breaker
# =====================================================================


class CircuitBreaker:
    """Async-compatible circuit breaker for a single external service.

    Thread-safety note: This implementation uses simple attribute
    assignments which are atomic in CPython (GIL).  For multi-process
    workers (Celery), each process gets its own circuit state, which
    is acceptable — each worker independently detects failures.

    Args:
        service: Human-readable name (e.g. ``"azure_openai"``).
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait in OPEN before transitioning to HALF_OPEN.
        excluded_exceptions: Exception types that should NOT count as failures
            (e.g. client-side validation errors, 4xx responses).
    """

    def __init__(
        self,
        service: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        excluded_exceptions: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.service = service
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.excluded_exceptions = excluded_exceptions

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._success_count: int = 0
        self._total_trips: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        """Current circuit state, with automatic OPEN → HALF_OPEN transition."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker HALF_OPEN — allowing probe call",
                    service=self.service,
                    elapsed_seconds=round(elapsed, 1),
                )
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def total_trips(self) -> int:
        """Total number of times the circuit has tripped to OPEN."""
        return self._total_trips

    @property
    def retry_after(self) -> float:
        """Seconds remaining until the circuit may transition to HALF_OPEN."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        remaining = self.recovery_timeout - elapsed
        return max(0.0, remaining)

    # ── State transitions ────────────────────────────────────────

    def record_success(self) -> None:
        """Record a successful call — resets failure count, closes circuit."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                "Circuit breaker CLOSED — probe call succeeded",
                service=self.service,
            )
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call — increments counter, may trip the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed — go straight back to OPEN
            self._state = CircuitState.OPEN
            self._total_trips += 1
            logger.warning(
                "Circuit breaker OPEN — probe call failed",
                service=self.service,
                recovery_timeout=self.recovery_timeout,
            )
        elif (
            self._state == CircuitState.CLOSED
            and self._failure_count >= self.failure_threshold
        ):
            self._state = CircuitState.OPEN
            self._total_trips += 1
            logger.warning(
                "Circuit breaker OPEN — failure threshold reached",
                service=self.service,
                failure_count=self._failure_count,
                threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
            )

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED (e.g. for admin override)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        logger.info("Circuit breaker manually reset", service=self.service)

    # ── Guard ────────────────────────────────────────────────────

    def _check_state(self) -> None:
        """Raise :class:`CircuitOpenError` if the circuit is OPEN."""
        current = self.state  # triggers OPEN → HALF_OPEN check
        if current == CircuitState.OPEN:
            raise CircuitOpenError(self.service, self.retry_after)
        # HALF_OPEN and CLOSED allow calls through

    # ── Async context manager ────────────────────────────────────

    async def __aenter__(self) -> CircuitBreaker:
        """Check circuit before executing the protected call."""
        self._check_state()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Record success or failure after the protected call.

        Returns False so exceptions propagate to the caller.
        """
        if exc_type is None:
            self.record_success()
        elif self.excluded_exceptions and issubclass(
            exc_type, self.excluded_exceptions
        ):
            # Excluded exceptions don't count as failures
            # (e.g. 400 Bad Request is a client error, not a service failure)
            pass
        else:
            self.record_failure()
        return False  # Don't suppress the exception

    # ── Decorator ────────────────────────────────────────────────

    def protect(
        self, fn: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        """Decorator that wraps an async function with circuit breaker protection.

        Usage::

            @circuit_breaker.protect
            async def call_external_service():
                ...
        """

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self:
                return await fn(*args, **kwargs)

        return wrapper

    # ── Repr ─────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(service={self.service!r}, "
            f"state={self.state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


# =====================================================================
# Pre-configured circuit breakers (plan.md spec)
# =====================================================================

# Lazily initialised singletons per service name
_breakers: dict[str, CircuitBreaker] = {}


def _ensure_default_breakers() -> None:
    """Create the default circuit breakers if they don't exist yet."""
    if _breakers:
        return

    # Azure OpenAI — 5 consecutive failures, 60s recovery
    _breakers["azure_openai"] = CircuitBreaker(
        "azure_openai",
        failure_threshold=5,
        recovery_timeout=60.0,
    )

    # SEC EDGAR — 10 consecutive failures, 300s recovery
    _breakers["sec_edgar"] = CircuitBreaker(
        "sec_edgar",
        failure_threshold=10,
        recovery_timeout=300.0,
    )

    # Qdrant — 3 consecutive failures, 30s recovery
    _breakers["qdrant"] = CircuitBreaker(
        "qdrant",
        failure_threshold=3,
        recovery_timeout=30.0,
    )

    logger.info(
        "Default circuit breakers initialised",
        services=list(_breakers.keys()),
    )


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Return the circuit breaker for the given service name.

    Creates default breakers on first call.  Returns the singleton
    instance for the requested service.

    Args:
        service: Service name — ``"azure_openai"``, ``"sec_edgar"``,
                 or ``"qdrant"``.

    Raises:
        KeyError: If no circuit breaker is registered for the service.
    """
    _ensure_default_breakers()
    if service not in _breakers:
        raise KeyError(
            f"No circuit breaker registered for {service!r}. "
            f"Available: {list(_breakers.keys())}"
        )
    return _breakers[service]


def register_circuit_breaker(
    service: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    excluded_exceptions: tuple[type[BaseException], ...] = (),
) -> CircuitBreaker:
    """Register a custom circuit breaker for a service.

    Useful for tests or services with non-default thresholds.

    Args:
        service: Service name.
        failure_threshold: Consecutive failures before opening.
        recovery_timeout: Seconds before half-open probe.
        excluded_exceptions: Exceptions that don't count as failures.

    Returns:
        The newly created :class:`CircuitBreaker`.
    """
    _ensure_default_breakers()
    cb = CircuitBreaker(
        service,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        excluded_exceptions=excluded_exceptions,
    )
    _breakers[service] = cb
    logger.info(
        "Circuit breaker registered",
        service=service,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )
    return cb


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Return all registered circuit breakers (useful for health/status endpoints)."""
    _ensure_default_breakers()
    return dict(_breakers)


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to CLOSED (useful for testing)."""
    for cb in _breakers.values():
        cb.reset()
