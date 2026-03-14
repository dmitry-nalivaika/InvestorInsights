# filepath: backend/tests/unit/test_qdrant_unavailable.py
"""Unit tests for Qdrant unavailable degradation (T819).

Verifies:
  - VectorStoreClient.search() wraps connection errors as VectorStoreUnavailableError
  - CompanyChatAgent emits a distinct unavailability message (not the no-results message)
  - Non-connection errors (e.g. 404 UnexpectedResponse) still propagate normally
  - Other retrieval errors still fall through to empty chunks / no-results
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

# Set env vars BEFORE any app imports
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.clients.qdrant_client import VectorStoreClient, VectorStoreUnavailableError
from app.rag.chat_agent import (
    CompanyChatAgent,
    DoneEvent,
    SourcesEvent,
    TokenEvent,
    _NO_RESULTS_MESSAGE,
    _VECTOR_STORE_UNAVAILABLE_MESSAGE,
)


# =====================================================================
# Helpers
# =====================================================================

COMPANY_ID = uuid.uuid4()
FAKE_VECTOR = [0.1] * 3072


def _make_qdrant_client() -> VectorStoreClient:
    """Create a VectorStoreClient with a mocked async Qdrant SDK client."""
    with patch("app.clients.qdrant_client.AsyncQdrantClient"):
        client = VectorStoreClient()
    return client


def _make_chat_agent(
    *,
    retrieval_service: AsyncMock | None = None,
    openai_client: MagicMock | None = None,
) -> CompanyChatAgent:
    """Create a CompanyChatAgent with mocked dependencies."""
    mock_openai = openai_client or MagicMock()
    mock_openai.chat_model = "gpt-4o"

    mock_retrieval = retrieval_service or AsyncMock()

    return CompanyChatAgent(
        company_id=COMPANY_ID,
        company_name="Test Corp",
        ticker="TST",
        openai_client=mock_openai,
        retrieval_service=mock_retrieval,
    )


async def _collect_events(agent: CompanyChatAgent, question: str) -> list:
    """Collect all events from generate_response into a list."""
    events = []
    async for event in agent.generate_response(question):
        events.append(event)
    return events


# =====================================================================
# VectorStoreClient.search() — connection error wrapping (T819)
# =====================================================================


class TestQdrantSearchConnectionErrors:
    """VectorStoreClient.search() wraps connection failures as VectorStoreUnavailableError."""

    @pytest.mark.asyncio
    async def test_connect_error_raises_unavailable(self) -> None:
        """httpx.ConnectError → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="Connection refused"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_connect_timeout_raises_unavailable(self) -> None:
        """httpx.ConnectTimeout → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=httpx.ConnectTimeout("Timed out connecting"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="Timed out"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_read_timeout_raises_unavailable(self) -> None:
        """httpx.ReadTimeout (subclass of TimeoutException) → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=httpx.ReadTimeout("Read timed out"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="Read timed out"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_response_handling_exception_raises_unavailable(self) -> None:
        """ResponseHandlingException → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=ResponseHandlingException("bad response"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="bad response"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_connection_error_raises_unavailable(self) -> None:
        """Built-in ConnectionError → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=ConnectionError("Connection reset by peer"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="Connection reset"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_os_error_raises_unavailable(self) -> None:
        """OSError (e.g. socket error) → VectorStoreUnavailableError."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=OSError("Network is unreachable"),
        )

        with pytest.raises(VectorStoreUnavailableError, match="Network is unreachable"):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_unexpected_response_not_wrapped(self) -> None:
        """UnexpectedResponse (e.g. 404) is NOT wrapped — it propagates as-is."""
        client = _make_qdrant_client()
        client._client.query_points = AsyncMock(
            side_effect=UnexpectedResponse(
                status_code=404,
                reason_phrase="Not Found",
                content=b"collection not found",
                headers={},
            ),
        )

        with pytest.raises(UnexpectedResponse):
            await client.search(COMPANY_ID, FAKE_VECTOR)

    @pytest.mark.asyncio
    async def test_original_exception_chained(self) -> None:
        """The original exception is chained via __cause__."""
        client = _make_qdrant_client()
        original = httpx.ConnectError("refused")
        client._client.query_points = AsyncMock(side_effect=original)

        with pytest.raises(VectorStoreUnavailableError) as exc_info:
            await client.search(COMPANY_ID, FAKE_VECTOR)

        assert exc_info.value.__cause__ is original

    @pytest.mark.asyncio
    async def test_successful_search_not_affected(self) -> None:
        """Normal successful search still returns results."""
        client = _make_qdrant_client()
        mock_result = MagicMock()
        mock_result.points = [MagicMock(id="pt1", score=0.9, payload={"text": "hello"})]
        client._client.query_points = AsyncMock(return_value=mock_result)

        results = await client.search(COMPANY_ID, FAKE_VECTOR)
        assert len(results) == 1
        assert results[0].id == "pt1"


# =====================================================================
# CompanyChatAgent — vector store unavailable yields distinct message
# =====================================================================


class TestChatAgentQdrantUnavailable:
    """CompanyChatAgent emits a distinct message when Qdrant is down (T819)."""

    @pytest.mark.asyncio
    async def test_unavailable_yields_distinct_message(self) -> None:
        """VectorStoreUnavailableError → unavailable message, NOT no-results."""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            side_effect=VectorStoreUnavailableError("Qdrant is down"),
        )
        agent = _make_chat_agent(retrieval_service=mock_retrieval)

        events = await _collect_events(agent, "What was revenue in 2024?")

        # Should yield SourcesEvent, TokenEvent, DoneEvent
        assert len(events) == 3
        assert isinstance(events[0], SourcesEvent)
        assert events[0].sources == []
        assert isinstance(events[1], TokenEvent)
        assert events[1].token == _VECTOR_STORE_UNAVAILABLE_MESSAGE
        assert isinstance(events[2], DoneEvent)
        assert events[2].full_text == _VECTOR_STORE_UNAVAILABLE_MESSAGE
        assert events[2].error is not None
        assert "Qdrant is down" in events[2].error

    @pytest.mark.asyncio
    async def test_unavailable_message_differs_from_no_results(self) -> None:
        """The unavailable message is distinct from the no-results message."""
        assert _VECTOR_STORE_UNAVAILABLE_MESSAGE != _NO_RESULTS_MESSAGE
        assert "temporarily unavailable" in _VECTOR_STORE_UNAVAILABLE_MESSAGE
        assert "vector database" in _VECTOR_STORE_UNAVAILABLE_MESSAGE

    @pytest.mark.asyncio
    async def test_generic_retrieval_error_falls_through_to_no_results(self) -> None:
        """A non-VectorStoreUnavailableError still falls through to empty chunks → no-results."""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            side_effect=RuntimeError("Something else broke"),
        )
        agent = _make_chat_agent(retrieval_service=mock_retrieval)

        events = await _collect_events(agent, "What was revenue in 2024?")

        # Should yield no-results path (SourcesEvent → TokenEvent → DoneEvent)
        assert len(events) == 3
        assert isinstance(events[1], TokenEvent)
        assert events[1].token == _NO_RESULTS_MESSAGE
        # DoneEvent should NOT have an error field set
        assert isinstance(events[2], DoneEvent)
        assert events[2].error is None

    @pytest.mark.asyncio
    async def test_unavailable_does_not_call_llm(self) -> None:
        """When Qdrant is unavailable, the LLM is never called."""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            side_effect=VectorStoreUnavailableError("down"),
        )
        mock_openai = MagicMock()
        mock_openai.chat_model = "gpt-4o"
        mock_openai.chat_completion_stream = AsyncMock()

        agent = _make_chat_agent(
            retrieval_service=mock_retrieval,
            openai_client=mock_openai,
        )

        await _collect_events(agent, "What was revenue?")

        mock_openai.chat_completion_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_unavailable_model_field_set(self) -> None:
        """DoneEvent still includes the model name even on unavailability."""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            side_effect=VectorStoreUnavailableError("down"),
        )
        agent = _make_chat_agent(retrieval_service=mock_retrieval)

        events = await _collect_events(agent, "Tell me about the 10-K")
        done = events[-1]

        assert isinstance(done, DoneEvent)
        assert done.model == "gpt-4o"
        assert done.citations == []
        assert done.token_count > 0


# =====================================================================
# VectorStoreUnavailableError exception class
# =====================================================================


class TestVectorStoreUnavailableError:
    """Tests for the exception class itself."""

    def test_default_message(self) -> None:
        exc = VectorStoreUnavailableError()
        assert str(exc) == "Vector store is unavailable"

    def test_custom_message(self) -> None:
        exc = VectorStoreUnavailableError("Qdrant timed out")
        assert str(exc) == "Qdrant timed out"

    def test_is_exception(self) -> None:
        assert issubclass(VectorStoreUnavailableError, Exception)
