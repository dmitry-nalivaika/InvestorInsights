# filepath: backend/tests/unit/test_query_expansion.py
"""Unit tests for query expansion graceful degradation (T413a).

FR-409: Query expansion failure MUST NOT block or delay chat response.
"""

from __future__ import annotations

import os

os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.clients.openai_client import (
    ChatResponse,
    LLMError,
    LLMUnavailableError,
    TokenUsage,
)
from app.services.retrieval_service import RetrievalService


@pytest.fixture()
def mock_openai() -> MagicMock:
    """Mock OpenAI client."""
    client = MagicMock()
    client.embed_texts = AsyncMock(return_value=[[0.1] * 3072])
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture()
def mock_qdrant() -> MagicMock:
    """Mock Qdrant client."""
    client = MagicMock()
    client.search = AsyncMock(return_value=[])
    return client


@pytest.fixture()
def service(mock_openai: MagicMock, mock_qdrant: MagicMock) -> RetrievalService:
    """RetrievalService with mocked dependencies."""
    return RetrievalService(
        company_id=uuid.uuid4(),
        openai_client=mock_openai,
        vector_store=mock_qdrant,
    )


class TestQueryExpansionGracefulDegradation:
    """FR-409: Query expansion failure must fall back gracefully."""

    @pytest.mark.asyncio()
    async def test_expansion_success(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """When expansion succeeds, multiple queries are used."""
        mock_openai.chat_completion.return_value = ChatResponse(
            content="What is the revenue trend?\nHow did sales change?",
            finish_reason="stop",
            model="gpt-4o-mini",
            usage=TokenUsage(10, 20, 30),
        )
        mock_openai.embed_texts.return_value = [
            [0.1] * 3072,
            [0.2] * 3072,
            [0.3] * 3072,
        ]

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        await service.retrieve("What is revenue?", config=config)

        # Should embed original + 2 expanded queries
        assert mock_openai.embed_texts.call_count == 1
        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 3  # original + 2 expansions

    @pytest.mark.asyncio()
    async def test_expansion_llm_error_falls_back(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """LLMError during expansion → falls back to original query only."""
        mock_openai.chat_completion.side_effect = LLMError("timeout")

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        await service.retrieve("What is revenue?", config=config)

        # Should still embed and search with original query
        assert mock_openai.embed_texts.call_count == 1
        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 1  # only original

    @pytest.mark.asyncio()
    async def test_expansion_unavailable_falls_back(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """LLMUnavailableError during expansion → falls back gracefully."""
        mock_openai.chat_completion.side_effect = LLMUnavailableError(
            "Service unavailable"
        )

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        await service.retrieve("What is revenue?", config=config)

        # Falls back to original query
        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 1

    @pytest.mark.asyncio()
    async def test_expansion_generic_exception_falls_back(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """Generic exception during expansion → falls back gracefully."""
        mock_openai.chat_completion.side_effect = RuntimeError("unexpected")

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        await service.retrieve("What is revenue?", config=config)

        # Falls back to original query
        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 1

    @pytest.mark.asyncio()
    async def test_expansion_disabled(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """When query_expansion=False, no expansion LLM call is made."""
        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=False)
        await service.retrieve("What is revenue?", config=config)

        # chat_completion should NOT have been called for expansion
        mock_openai.chat_completion.assert_not_called()
        # Only original query embedded
        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 1

    @pytest.mark.asyncio()
    async def test_expansion_limits_to_3(
        self, service: RetrievalService, mock_openai: MagicMock,
    ) -> None:
        """Query expansion returns at most 3 alternative queries."""
        mock_openai.chat_completion.return_value = ChatResponse(
            content="Q1\nQ2\nQ3\nQ4\nQ5",
            finish_reason="stop",
            model="gpt-4o-mini",
            usage=TokenUsage(10, 20, 30),
        )
        # Return enough embeddings for original + 3 expansions
        mock_openai.embed_texts.return_value = [
            [0.1] * 3072, [0.2] * 3072, [0.3] * 3072, [0.4] * 3072,
        ]

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        await service.retrieve("Test query", config=config)

        texts = mock_openai.embed_texts.call_args[0][0]
        assert len(texts) == 4  # original + max 3 expansions


class TestRetrievalDeduplication:
    """Tests for result deduplication and re-ranking."""

    @pytest.mark.asyncio()
    async def test_dedup_by_chunk_id(
        self, service: RetrievalService, mock_openai: MagicMock, mock_qdrant: MagicMock,
    ) -> None:
        """Duplicate chunk IDs are deduplicated, keeping max score."""
        chunk_id = str(uuid.uuid4())

        # Two search results with same chunk_id but different scores
        point1 = MagicMock()
        point1.id = chunk_id
        point1.score = 0.8
        point1.payload = {"text": "chunk text", "doc_type": "10-K"}

        point2 = MagicMock()
        point2.id = chunk_id
        point2.score = 0.95
        point2.payload = {"text": "chunk text", "doc_type": "10-K"}

        mock_qdrant.search.side_effect = [[point1], [point2]]
        mock_openai.embed_texts.return_value = [[0.1] * 3072, [0.2] * 3072]

        # Enable expansion to get multiple search calls
        mock_openai.chat_completion.return_value = ChatResponse(
            content="Expanded query",
            finish_reason="stop",
            model="gpt-4o-mini",
            usage=TokenUsage(10, 20, 30),
        )

        from app.schemas.chat import RetrievalConfig
        config = RetrievalConfig(query_expansion=True)
        results = await service.retrieve("test", config=config)

        # Should have only 1 chunk (deduped)
        assert len(results) == 1
        # Should keep the higher score
        assert results[0].score == 0.95


class TestYearRangeBuilder:
    """Tests for year range filter construction."""

    def test_no_range(self) -> None:
        result = RetrievalService._build_year_range(None, None)
        assert result is None

    def test_min_only(self) -> None:
        result = RetrievalService._build_year_range(2020, None)
        assert result is not None
        assert 2020 in result
        assert 2100 in result

    def test_max_only(self) -> None:
        result = RetrievalService._build_year_range(None, 2023)
        assert result is not None
        assert 1990 in result
        assert 2023 in result

    def test_both(self) -> None:
        result = RetrievalService._build_year_range(2020, 2023)
        assert result == [2020, 2021, 2022, 2023]

    def test_swapped(self) -> None:
        result = RetrievalService._build_year_range(2023, 2020)
        assert result == [2020, 2021, 2022, 2023]
