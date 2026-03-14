# filepath: backend/app/services/retrieval_service.py
"""Semantic retrieval service for RAG chat.

Handles:
  - Query embedding generation
  - Qdrant similarity search with metadata filters (T402, T410)
  - LLM-based query expansion with graceful degradation (T415, FR-409)
  - Result deduplication and re-ranking
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.clients.openai_client import LLMError, get_openai_client
from app.clients.qdrant_client import (
    PAYLOAD_DOC_TYPE,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_FISCAL_YEAR,
    PAYLOAD_SECTION_KEY,
    PAYLOAD_SECTION_TITLE,
    PAYLOAD_TEXT,
    PAYLOAD_TOKEN_COUNT,
    get_qdrant_client,
)
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from app.clients.openai_client import OpenAIClient
    from app.clients.qdrant_client import VectorStoreClient
    from app.schemas.chat import RetrievalConfig

logger = get_logger(__name__)

# ── Query expansion prompt ───────────────────────────────────────

_QUERY_EXPANSION_SYSTEM = (
    "You are a financial research query expansion assistant. "
    "Given a user question about SEC filings, generate 2-3 alternative search queries "
    "that would help retrieve relevant document chunks. "
    "Return ONLY the alternative queries, one per line, with no numbering or extra text."
)


# ── Source chunk schema ──────────────────────────────────────────


class RetrievedChunk:
    """A single retrieved context chunk with metadata."""

    __slots__ = (
        "chunk_id",
        "doc_type",
        "document_id",
        "fiscal_year",
        "score",
        "section_key",
        "section_title",
        "text",
        "token_count",
    )

    def __init__(
        self,
        *,
        chunk_id: str,
        text: str,
        score: float,
        document_id: str = "",
        doc_type: str = "",
        fiscal_year: int | None = None,
        section_key: str = "",
        section_title: str = "",
        token_count: int = 0,
    ) -> None:
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.document_id = document_id
        self.doc_type = doc_type
        self.fiscal_year = fiscal_year
        self.section_key = section_key
        self.section_title = section_title
        self.token_count = token_count

    def to_source_dict(self) -> dict[str, Any]:
        """Serialize to a source-citation dict for the SSE sources event."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "doc_type": self.doc_type,
            "fiscal_year": self.fiscal_year,
            "section_key": self.section_key,
            "section_title": self.section_title,
            "score": round(self.score, 4),
        }


# ── Service class ────────────────────────────────────────────────


class RetrievalService:
    """Handles semantic search + query expansion for the RAG pipeline.

    Instantiated per-request with the company context.
    """

    def __init__(
        self,
        company_id: uuid.UUID,
        *,
        openai_client: OpenAIClient | None = None,
        vector_store: VectorStoreClient | None = None,
    ) -> None:
        self._company_id = company_id
        self._openai = openai_client or get_openai_client()
        self._qdrant = vector_store or get_qdrant_client()

    # ── Public API ───────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        config: RetrievalConfig | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for a user query.

        1. Optionally expand the query via LLM (FR-409)
        2. Embed query (+ expanded queries)
        3. Search Qdrant with filters
        4. Deduplicate and re-rank by max score

        Args:
            query: The user's question.
            config: Optional retrieval tuning params.

        Returns:
            Sorted list of RetrievedChunk (highest score first).
        """
        from app.schemas.chat import RetrievalConfig as DefaultRetrievalConfig

        if config is None:
            config = DefaultRetrievalConfig()

        top_k = config.top_k
        score_threshold = config.score_threshold

        # Build filter params
        doc_types = config.filter_doc_types
        fiscal_years = self._build_year_range(
            config.filter_year_min, config.filter_year_max,
        )
        section_keys = config.filter_sections

        # Step 1: Query expansion (if enabled)
        queries = [query]
        if config.query_expansion:
            expanded = await self._expand_query(query)
            queries.extend(expanded)

        logger.info(
            "Retrieval starting",
            company_id=str(self._company_id),
            query_count=len(queries),
            top_k=top_k,
            score_threshold=score_threshold,
        )

        # Step 2 & 3: Embed all queries and search in parallel
        all_chunks: dict[str, RetrievedChunk] = {}

        # Embed all queries at once
        embeddings = await self._openai.embed_texts(queries)

        # Search for each query embedding concurrently
        search_tasks = [
            self._qdrant.search(
                self._company_id,
                embedding,
                top_k=top_k,
                score_threshold=score_threshold,
                doc_types=doc_types,
                fiscal_years=fiscal_years,
                section_keys=section_keys,
            )
            for embedding in embeddings
        ]
        search_results = await asyncio.gather(*search_tasks)

        # Step 4: Deduplicate by chunk_id, keep max score
        for results in search_results:
            for point in results:
                chunk_id = str(point.id)
                payload = point.payload or {}
                score = point.score

                existing = all_chunks.get(chunk_id)
                if existing is None or score > existing.score:
                    all_chunks[chunk_id] = RetrievedChunk(
                        chunk_id=chunk_id,
                        text=payload.get(PAYLOAD_TEXT, ""),
                        score=score,
                        document_id=payload.get(PAYLOAD_DOCUMENT_ID, ""),
                        doc_type=payload.get(PAYLOAD_DOC_TYPE, ""),
                        fiscal_year=payload.get(PAYLOAD_FISCAL_YEAR),
                        section_key=payload.get(PAYLOAD_SECTION_KEY, ""),
                        section_title=payload.get(PAYLOAD_SECTION_TITLE, ""),
                        token_count=payload.get(PAYLOAD_TOKEN_COUNT, 0),
                    )

        # Sort by score descending, take top_k
        ranked = sorted(all_chunks.values(), key=lambda c: c.score, reverse=True)
        final = ranked[:top_k]

        logger.info(
            "Retrieval complete",
            company_id=str(self._company_id),
            total_candidates=len(all_chunks),
            returned=len(final),
        )

        return final

    # ── Query expansion (FR-409) ─────────────────────────────────

    async def _expand_query(self, query: str) -> list[str]:
        """Generate 2-3 alternative queries via LLM.

        If the LLM call fails for any reason, returns an empty list
        (graceful degradation — FR-409: failure MUST NOT block chat).
        """
        try:
            response = await self._openai.chat_completion(
                messages=[
                    {"role": "system", "content": _QUERY_EXPANSION_SYSTEM},
                    {"role": "user", "content": query},
                ],
                temperature=0.7,
                max_tokens=256,
            )

            # Parse lines from response
            lines = [
                line.strip()
                for line in response.content.strip().split("\n")
                if line.strip()
            ]
            # Take at most 3 expansions
            expanded = lines[:3]

            logger.debug(
                "Query expansion succeeded",
                original=query,
                expanded_count=len(expanded),
            )
            return expanded

        except (LLMError, Exception) as exc:
            # FR-409: graceful degradation — fall back to original query
            logger.warning(
                "Query expansion failed, falling back to original query",
                error=str(exc),
                query=query[:100],
            )
            return []

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_year_range(
        year_min: int | None,
        year_max: int | None,
    ) -> list[int] | None:
        """Convert min/max year range to an explicit list for Qdrant MatchAny."""
        if year_min is None and year_max is None:
            return None
        low = year_min or 1990
        high = year_max or 2100
        if low > high:
            low, high = high, low
        return list(range(low, high + 1))
