# filepath: backend/app/clients/qdrant_client.py
"""
Qdrant vector store client wrapper.

Manages per-company collections (``company_{company_id}``),
vector upserts, similarity search with metadata filtering, and
collection lifecycle (create / delete / health).

Collection config from data-model.md:
  - Vectors: 3072 dims (text-embedding-3-large), Cosine distance
  - HNSW: m=16, ef_construct=100
  - on_disk_payload: True
  - Payload indexes: doc_type (keyword), fiscal_year (integer), section_key (keyword)

Usage::

    from app.clients.qdrant_client import get_qdrant_client
    client = get_qdrant_client()
    await client.upsert_vectors(company_id, points)
    results = await client.search(company_id, vector, filters, top_k)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import Settings, get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)


# =====================================================================
# Payload field constants (match data-model.md)
# =====================================================================

PAYLOAD_TEXT = "text"
PAYLOAD_COMPANY_ID = "company_id"
PAYLOAD_DOCUMENT_ID = "document_id"
PAYLOAD_DOC_TYPE = "doc_type"
PAYLOAD_FISCAL_YEAR = "fiscal_year"
PAYLOAD_FISCAL_QUARTER = "fiscal_quarter"
PAYLOAD_SECTION_KEY = "section_key"
PAYLOAD_SECTION_TITLE = "section_title"
PAYLOAD_FILING_DATE = "filing_date"
PAYLOAD_PERIOD_END_DATE = "period_end_date"
PAYLOAD_CHUNK_INDEX = "chunk_index"
PAYLOAD_TOKEN_COUNT = "token_count"


# =====================================================================
# Client class
# =====================================================================


class VectorStoreClient:
    """Async wrapper around the Qdrant Python SDK.

    Handles collection naming conventions, creation with the correct
    schema, point upsert/delete, and filtered similarity search.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        if settings is None:
            settings = get_settings()
        self._settings = settings
        self._prefix = settings.qdrant_collection_prefix
        self._dims = settings.embedding_dimensions

        url = settings.qdrant_url or f"http://{settings.qdrant_host}:{settings.qdrant_http_port}"
        self._client = AsyncQdrantClient(
            url=url,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,
            timeout=30,
        )

    # ── Collection naming ────────────────────────────────────────

    def collection_name(self, company_id: uuid.UUID | str) -> str:
        """Build the collection name for a company: ``{prefix}{company_id}``."""
        return f"{self._prefix}{company_id}"

    # ── Collection lifecycle ─────────────────────────────────────

    async def ensure_collection(self, company_id: uuid.UUID | str) -> None:
        """Create the per-company collection if it doesn't exist.

        Uses the canonical schema from data-model.md:
        Cosine distance, HNSW m=16 ef_construct=100, on_disk_payload.
        """
        name = self.collection_name(company_id)
        try:
            exists = await self._client.collection_exists(name)
            if exists:
                return
        except Exception:
            pass  # If check fails, try creating anyway

        logger.info("Creating Qdrant collection", collection=name, dimensions=self._dims)

        await self._client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=self._dims,
                distance=models.Distance.COSINE,
            ),
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
            on_disk_payload=True,
        )

        # Create payload indexes for filtered search
        await self._create_payload_indexes(name)

    async def _create_payload_indexes(self, collection_name: str) -> None:
        """Create payload field indexes for efficient filtered search."""
        keyword_fields = [PAYLOAD_DOC_TYPE, PAYLOAD_SECTION_KEY]
        integer_fields = [PAYLOAD_FISCAL_YEAR]

        for field in keyword_fields:
            try:
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except UnexpectedResponse:
                pass  # Index may already exist

        for field in integer_fields:
            try:
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.INTEGER,
                )
            except UnexpectedResponse:
                pass

    async def delete_collection(self, company_id: uuid.UUID | str) -> bool:
        """Delete the per-company collection. Returns True if deleted."""
        name = self.collection_name(company_id)
        try:
            result = await self._client.delete_collection(name)
            logger.info("Deleted Qdrant collection", collection=name)
            return bool(result)
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                return False
            raise

    async def collection_exists(self, company_id: uuid.UUID | str) -> bool:
        """Check whether the collection for a company exists."""
        name = self.collection_name(company_id)
        try:
            return await self._client.collection_exists(name)
        except Exception:
            return False

    async def collection_info(
        self, company_id: uuid.UUID | str
    ) -> Optional[Dict[str, Any]]:
        """Return collection metadata (point count, status, etc.)."""
        name = self.collection_name(company_id)
        try:
            info = await self._client.get_collection(name)
            return {
                "name": name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": str(info.status),
                "segments_count": info.segments_count,
            }
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                return None
            raise

    # ── Vector upsert / delete ───────────────────────────────────

    async def upsert_vectors(
        self,
        company_id: uuid.UUID | str,
        points: Sequence[models.PointStruct],
        *,
        batch_size: int = 100,
    ) -> None:
        """Upsert embedding points into the company's collection.

        Args:
            company_id: Company UUID.
            points: List of PointStruct (id, vector, payload).
            batch_size: Points per batch (Qdrant recommends ≤100).
        """
        name = self.collection_name(company_id)
        await self.ensure_collection(company_id)

        total = len(points)
        for i in range(0, total, batch_size):
            batch = points[i : i + batch_size]
            await self._client.upsert(
                collection_name=name,
                points=list(batch),
                wait=True,
            )
        logger.info(
            "Upserted vectors",
            collection=name,
            count=total,
        )

    async def delete_vectors_by_document(
        self,
        company_id: uuid.UUID | str,
        document_id: uuid.UUID | str,
    ) -> None:
        """Delete all points belonging to a specific document."""
        name = self.collection_name(company_id)
        await self._client.delete(
            collection_name=name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=PAYLOAD_DOCUMENT_ID,
                            match=models.MatchValue(value=str(document_id)),
                        ),
                    ]
                )
            ),
            wait=True,
        )
        logger.info(
            "Deleted vectors for document",
            collection=name,
            document_id=str(document_id),
        )

    # ── Search ───────────────────────────────────────────────────

    async def search(
        self,
        company_id: uuid.UUID | str,
        query_vector: List[float],
        *,
        top_k: int = 15,
        score_threshold: Optional[float] = None,
        doc_types: Optional[List[str]] = None,
        fiscal_years: Optional[List[int]] = None,
        section_keys: Optional[List[str]] = None,
    ) -> List[models.ScoredPoint]:
        """Semantic similarity search with optional metadata filters.

        Args:
            company_id: Company UUID.
            query_vector: Query embedding (3072-dim).
            top_k: Max results.
            score_threshold: Min cosine similarity score.
            doc_types: Filter by document type (e.g. ["10-K", "10-Q"]).
            fiscal_years: Filter by fiscal year (e.g. [2023, 2024]).
            section_keys: Filter by section key (e.g. ["item_1a", "item_7"]).

        Returns:
            List of ScoredPoint with payload.
        """
        name = self.collection_name(company_id)
        must_conditions: List[models.Condition] = []

        if doc_types:
            must_conditions.append(
                models.FieldCondition(
                    key=PAYLOAD_DOC_TYPE,
                    match=models.MatchAny(any=doc_types),
                )
            )
        if fiscal_years:
            must_conditions.append(
                models.FieldCondition(
                    key=PAYLOAD_FISCAL_YEAR,
                    match=models.MatchAny(any=fiscal_years),
                )
            )
        if section_keys:
            must_conditions.append(
                models.FieldCondition(
                    key=PAYLOAD_SECTION_KEY,
                    match=models.MatchAny(any=section_keys),
                )
            )

        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        results = await self._client.query_points(
            collection_name=name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return results.points

    # ── Scroll (batch retrieval) ─────────────────────────────────

    async def scroll(
        self,
        company_id: uuid.UUID | str,
        *,
        document_id: Optional[str] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> tuple[List[models.Record], Optional[str]]:
        """Scroll through points in a collection.

        Returns (records, next_offset). next_offset is None when done.
        """
        name = self.collection_name(company_id)
        conditions: List[models.Condition] = []
        if document_id:
            conditions.append(
                models.FieldCondition(
                    key=PAYLOAD_DOCUMENT_ID,
                    match=models.MatchValue(value=document_id),
                )
            )

        scroll_filter = models.Filter(must=conditions) if conditions else None

        records, next_offset = await self._client.scroll(
            collection_name=name,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        return records, next_offset

    # ── Health ───────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if Qdrant is reachable."""
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False

    # ── Cleanup ──────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# =====================================================================
# Module-level singleton
# =====================================================================

_qdrant_client: Optional[VectorStoreClient] = None


def init_qdrant_client(settings: Optional[Settings] = None) -> VectorStoreClient:
    """Initialise the module-level Qdrant client singleton."""
    global _qdrant_client  # noqa: PLW0603
    _qdrant_client = VectorStoreClient(settings)
    logger.info("Qdrant client initialised")
    return _qdrant_client


async def close_qdrant_client() -> None:
    """Close the module-level Qdrant client."""
    global _qdrant_client  # noqa: PLW0603
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None


def get_qdrant_client() -> VectorStoreClient:
    """Return the module-level Qdrant client. Must be initialised first."""
    if _qdrant_client is None:
        raise RuntimeError(
            "Qdrant client not initialised — call init_qdrant_client() at startup"
        )
    return _qdrant_client
