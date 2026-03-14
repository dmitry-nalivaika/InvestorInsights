# filepath: backend/app/clients/openai_client.py
"""
Azure OpenAI / OpenAI client wrapper.

Provides a unified async interface for:
  - **Embeddings**: ``text-embedding-3-large`` (3072 dims) with batching
  - **Chat completions**: Streaming and non-streaming with configurable
    model, temperature, max_tokens
  - **Health check**: Lightweight probe for the ``/health`` endpoint

Supports both Azure OpenAI (primary) and direct OpenAI (fallback)
based on the ``LLM_PROVIDER`` setting.

Retry policy (from plan.md):
  - Max retries: 3
  - Backoff: Exponential (1s, 2s, 4s)
  - Retry on: 429, 500, 502, 503, timeout

Config references:
  - ``Settings.llm_provider`` — ``azure_openai`` or ``openai``
  - ``Settings.azure_openai_*`` — Azure-specific config
  - ``Settings.openai_api_key`` — Direct OpenAI fallback
  - ``Settings.llm_*`` / ``Settings.embedding_*`` — model params

Usage::

    from app.clients.openai_client import get_openai_client
    client = get_openai_client()
    embeddings = await client.embed_texts(["chunk 1", "chunk 2"])
    response = await client.chat_completion(messages=[...])
    async for chunk in client.chat_completion_stream(messages=[...]):
        print(chunk)
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    RateLimitError,
)

from app.config import LLMProvider, Settings, get_settings
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from openai.types.chat import ChatCompletion

logger = get_logger(__name__)

# =====================================================================
# Retry configuration (plan.md — Azure OpenAI retry policy)
# =====================================================================

_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


# =====================================================================
# Type aliases
# =====================================================================

ChatMessage = dict[str, str]  # {"role": "...", "content": "..."}


# =====================================================================
# Custom exceptions
# =====================================================================


class LLMError(Exception):
    """Raised on non-retryable LLM API errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.provider = provider
        super().__init__(message)


class LLMUnavailableError(LLMError):
    """Raised when the LLM service is unavailable after exhausting retries."""


# =====================================================================
# Token usage tracking
# =====================================================================


class TokenUsage:
    """Simple token usage tracker returned from completions."""

    __slots__ = ("completion_tokens", "prompt_tokens", "total_tokens")

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


# =====================================================================
# Chat completion response wrapper
# =====================================================================


class ChatResponse:
    """Wraps a non-streaming chat completion result."""

    __slots__ = ("content", "finish_reason", "model", "usage")

    def __init__(
        self,
        content: str,
        finish_reason: str | None,
        model: str,
        usage: TokenUsage,
    ) -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.model = model
        self.usage = usage


# =====================================================================
# Streaming chunk wrapper
# =====================================================================


class StreamChunk:
    """Wraps a single token/chunk from a streaming completion."""

    __slots__ = ("content", "finish_reason", "model")

    def __init__(
        self,
        content: str,
        finish_reason: str | None = None,
        model: str = "",
    ) -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.model = model


# =====================================================================
# Client class
# =====================================================================


class OpenAIClient:
    """Async wrapper around the OpenAI SDK supporting Azure and direct providers.

    Provides embedding, chat completion (streaming & non-streaming),
    and health-check functionality with automatic retries.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._provider = settings.llm_provider

        # Model / deployment names
        self._chat_model = settings.azure_openai_chat_deployment
        self._embedding_model = settings.azure_openai_embedding_deployment
        self._embedding_dimensions = settings.embedding_dimensions
        self._embedding_batch_size = settings.embedding_batch_size

        # LLM defaults
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._timeout = settings.llm_timeout

        # Build the appropriate SDK client
        self._client = self._build_client(settings)
        logger.info(
            "OpenAI client initialised",
            provider=self._provider.value,
            chat_model=self._chat_model,
            embedding_model=self._embedding_model,
            embedding_dimensions=self._embedding_dimensions,
        )

    # ── Client factory ───────────────────────────────────────────

    @staticmethod
    def _build_client(settings: Settings) -> AsyncAzureOpenAI | AsyncOpenAI:
        """Construct the correct async OpenAI SDK client based on provider."""
        if settings.llm_provider == LLMProvider.AZURE_OPENAI:
            return AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint or "",
                api_version=settings.azure_openai_api_version,
                timeout=float(settings.llm_timeout),
                max_retries=0,  # We handle retries ourselves
            )
        else:
            return AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=float(settings.llm_timeout),
                max_retries=0,
            )

    # ── Retry helper ─────────────────────────────────────────────

    async def _retry(
        self,
        operation: str,
        fn: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute ``fn`` with exponential backoff retries.

        Args:
            operation: Human-readable label for logging.
            fn: Async callable to execute.
            *args, **kwargs: Passed through to ``fn``.

        Returns:
            The result of ``fn(*args, **kwargs)``.

        Raises:
            LLMUnavailableError: After exhausting all retries.
            LLMError: On non-retryable errors.
        """
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await fn(*args, **kwargs)

            except RateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    # Check for Retry-After header
                    retry_headers = getattr(exc, "headers", None) or {}
                    wait = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                    if isinstance(retry_headers, dict):
                        ra_value = retry_headers.get("retry-after") or retry_headers.get("Retry-After")
                        if ra_value:
                            with contextlib.suppress(ValueError, TypeError):
                                wait = min(float(ra_value), 60.0)
                    logger.warning(
                        "LLM rate limited, retrying",
                        operation=operation,
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        provider=self._provider.value,
                    )
                    await asyncio.sleep(wait)
                    continue

            except APIStatusError as exc:
                last_exc = exc
                status = exc.status_code
                if status in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    wait = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        "LLM retryable error",
                        operation=operation,
                        status=status,
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        provider=self._provider.value,
                    )
                    await asyncio.sleep(wait)
                    continue
                # Non-retryable status
                raise LLMError(
                    f"LLM API error: HTTP {status} — {exc.message}",
                    status_code=status,
                    provider=self._provider.value,
                ) from exc

            except (APIConnectionError, APITimeoutError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        "LLM connection/timeout error, retrying",
                        operation=operation,
                        error=str(exc),
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        provider=self._provider.value,
                    )
                    await asyncio.sleep(wait)
                    continue

            except Exception as exc:
                # Unexpected error — don't retry
                raise LLMError(
                    f"Unexpected LLM error during {operation}: {exc}",
                    provider=self._provider.value,
                ) from exc

        raise LLMUnavailableError(
            f"LLM unavailable after {_MAX_RETRIES} retries for {operation}",
            provider=self._provider.value,
        ) from last_exc

    # ── Embeddings ───────────────────────────────────────────────

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts with automatic batching.

        Args:
            texts: Input texts to embed.
            model: Override the default embedding model/deployment.
            dimensions: Override the default embedding dimensions.

        Returns:
            List of embedding vectors (one per input text), in the same order.

        Raises:
            LLMError: On non-retryable API errors.
            LLMUnavailableError: After exhausting retries.
        """
        if not texts:
            return []

        model_name = model or self._embedding_model
        dims = dimensions or self._embedding_dimensions
        batch_size = self._embedding_batch_size
        all_embeddings: list[list[float]] = [[] for _ in texts]

        # Process in batches (plan.md: batch_size = 64)
        for batch_start in range(0, len(texts), batch_size):
            batch = texts[batch_start : batch_start + batch_size]
            batch_indices = list(range(batch_start, batch_start + len(batch)))

            start_time = time.monotonic()

            response = await self._retry(
                "embed_texts",
                self._client.embeddings.create,
                input=list(batch),
                model=model_name,
                dimensions=dims,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Extract embeddings in order
            for item in response.data:
                idx = batch_indices[item.index]
                all_embeddings[idx] = item.embedding

            logger.debug(
                "Embedding batch completed",
                batch_size=len(batch),
                model=model_name,
                dimensions=dims,
                duration_ms=round(duration_ms, 1),
                total_tokens=getattr(response.usage, "total_tokens", 0),
            )

        logger.info(
            "Embeddings generated",
            count=len(texts),
            model=model_name,
            dimensions=dims,
            batches=(len(texts) + batch_size - 1) // batch_size,
        )

        return all_embeddings

    async def embed_text(
        self,
        text: str,
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[float]:
        """Generate an embedding for a single text.

        Convenience wrapper around :meth:`embed_texts`.
        """
        results = await self.embed_texts([text], model=model, dimensions=dimensions)
        return results[0]

    # ── Chat completion (non-streaming) ──────────────────────────

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ChatResponse:
        """Generate a chat completion (non-streaming).

        Args:
            messages: List of chat messages (system/user/assistant).
            model: Override the default chat model/deployment.
            temperature: Override the default temperature.
            max_tokens: Override the default max_tokens.
            stop: Optional stop sequences.

        Returns:
            ChatResponse with content, finish_reason, model, and token usage.

        Raises:
            LLMError: On non-retryable API errors.
            LLMUnavailableError: After exhausting retries.
        """
        model_name = model or self._chat_model
        temp = temperature if temperature is not None else self._temperature
        tokens = max_tokens or self._max_tokens

        start_time = time.monotonic()

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": False,
        }
        if stop:
            kwargs["stop"] = stop

        response: ChatCompletion = await self._retry(
            "chat_completion",
            self._client.chat.completions.create,
            **kwargs,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        choice = response.choices[0] if response.choices else None
        content = choice.message.content or "" if choice else ""
        finish_reason = choice.finish_reason if choice else None

        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        logger.info(
            "Chat completion generated",
            model=response.model,
            finish_reason=finish_reason,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            duration_ms=round(duration_ms, 1),
        )

        return ChatResponse(
            content=content,
            finish_reason=finish_reason,
            model=response.model,
            usage=usage,
        )

    # ── Chat completion (streaming — FR-403) ─────────────────────

    async def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming chat completion (FR-403: token-by-token SSE).

        Args:
            messages: List of chat messages (system/user/assistant).
            model: Override the default chat model/deployment.
            temperature: Override the default temperature.
            max_tokens: Override the default max_tokens.
            stop: Optional stop sequences.

        Yields:
            StreamChunk objects with incremental content and finish_reason.

        Raises:
            LLMError: On non-retryable API errors.
            LLMUnavailableError: After exhausting retries.
        """
        model_name = model or self._chat_model
        temp = temperature if temperature is not None else self._temperature
        tokens = max_tokens or self._max_tokens

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": True,
        }
        if stop:
            kwargs["stop"] = stop

        start_time = time.monotonic()

        # The retry wrapper returns the async stream object;
        # iteration happens outside the retry boundary because
        # we can't restart a half-consumed stream on failure.
        stream = await self._retry(
            "chat_completion_stream",
            self._client.chat.completions.create,
            **kwargs,
        )

        chunk_count = 0
        try:
            async for event in stream:  # type: ChatCompletionChunk
                choice = event.choices[0] if event.choices else None
                if choice is None:
                    continue

                delta_content = choice.delta.content or ""
                finish = choice.finish_reason

                if delta_content or finish:
                    chunk_count += 1
                    yield StreamChunk(
                        content=delta_content,
                        finish_reason=finish,
                        model=event.model or model_name,
                    )
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Streaming completion finished",
                model=model_name,
                chunks=chunk_count,
                duration_ms=round(duration_ms, 1),
            )

    # ── Health check ─────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if the LLM API is reachable.

        Uses a minimal embedding call with a short text to verify
        connectivity without consuming significant tokens.
        """
        try:
            result = await self._client.embeddings.create(
                input=["health"],
                model=self._embedding_model,
                dimensions=self._embedding_dimensions,
            )
            return len(result.data) > 0
        except Exception as exc:
            logger.warning(
                "LLM health check failed",
                error=str(exc),
                provider=self._provider.value,
            )
            return False

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        with contextlib.suppress(Exception):
            await self._client.close()

    @property
    def provider(self) -> str:
        """Return the current provider name."""
        return self._provider.value

    @property
    def chat_model(self) -> str:
        """Return the current chat model/deployment name."""
        return self._chat_model

    @property
    def embedding_model(self) -> str:
        """Return the current embedding model/deployment name."""
        return self._embedding_model


# =====================================================================
# Module-level singleton
# =====================================================================

_openai_client: OpenAIClient | None = None


def init_openai_client(settings: Settings | None = None) -> OpenAIClient:
    """Initialise the module-level OpenAI client singleton."""
    global _openai_client
    _openai_client = OpenAIClient(settings)
    logger.info(
        "OpenAI client singleton initialised",
        provider=_openai_client.provider,
    )
    return _openai_client


async def close_openai_client() -> None:
    """Close the module-level OpenAI client."""
    global _openai_client
    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
        logger.info("OpenAI client singleton closed")


def get_openai_client() -> OpenAIClient:
    """Return the module-level OpenAI client. Must be initialised first."""
    if _openai_client is None:
        raise RuntimeError(
            "OpenAI client not initialised — call init_openai_client() at startup"
        )
    return _openai_client
