# filepath: backend/app/ingestion/embedder.py
"""Embedding service for document chunks.

Generates embeddings via Azure OpenAI (text-embedding-3-large)
and upserts them to Qdrant with metadata payloads.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from qdrant_client import models as qdrant_models

from app.clients.openai_client import OpenAIClient, get_openai_client
from app.clients.qdrant_client import (
    PAYLOAD_CHUNK_INDEX,
    PAYLOAD_COMPANY_ID,
    PAYLOAD_DOC_TYPE,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_FILING_DATE,
    PAYLOAD_FISCAL_QUARTER,
    PAYLOAD_FISCAL_YEAR,
    PAYLOAD_PERIOD_END_DATE,
    PAYLOAD_SECTION_KEY,
    PAYLOAD_SECTION_TITLE,
    PAYLOAD_TEXT,
    PAYLOAD_TOKEN_COUNT,
    VectorStoreClient,
    get_qdrant_client,
)
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.ingestion.chunker import Chunk

logger = get_logger(__name__)


class EmbeddingResult:
    """Result of batch embedding + upsert."""

    __slots__ = ("vectors_upserted", "embedding_model", "dimensions")

    def __init__(
        self,
        vectors_upserted: int,
        embedding_model: str,
        dimensions: int,
    ) -> None:
        self.vectors_upserted = vectors_upserted
        self.embedding_model = embedding_model
        self.dimensions = dimensions


async def embed_and_upsert_chunks(
    chunks: list[Chunk],
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
    fiscal_year: int,
    fiscal_quarter: int | None = None,
    filing_date: str | None = None,
    period_end_date: str | None = None,
    *,
    openai_client: OpenAIClient | None = None,
    vector_store: VectorStoreClient | None = None,
    batch_size: int = 64,
) -> EmbeddingResult:
    """Generate embeddings for chunks and upsert to Qdrant.

    Args:
        chunks: List of text chunks to embed.
        company_id: Company UUID.
        document_id: Document UUID.
        doc_type: Filing type (e.g. "10-K").
        fiscal_year: Fiscal year.
        fiscal_quarter: Fiscal quarter (optional).
        filing_date: Filing date string.
        period_end_date: Period end date string.
        openai_client: Optional client override (for testing).
        vector_store: Optional vector store override (for testing).
        batch_size: Embedding batch size.

    Returns:
        EmbeddingResult with count of vectors upserted.
    """
    if not chunks:
        return EmbeddingResult(vectors_upserted=0, embedding_model="", dimensions=0)

    oai = openai_client or get_openai_client()
    qdrant = vector_store or get_qdrant_client()

    # Ensure collection exists
    await qdrant.ensure_collection(company_id)

    # Extract texts for embedding
    texts = [chunk.content for chunk in chunks]

    # Generate embeddings in batches
    logger.info(
        "Generating embeddings",
        chunk_count=len(texts),
        company_id=str(company_id),
        document_id=str(document_id),
    )
    embeddings = await oai.embed_texts(texts)

    # Build Qdrant points with metadata
    points: list[qdrant_models.PointStruct] = []
    vector_ids: list[str] = []

    for chunk, embedding in zip(chunks, embeddings):
        vector_id = str(uuid.uuid4())
        vector_ids.append(vector_id)

        payload: dict[str, Any] = {
            PAYLOAD_TEXT: chunk.content,
            PAYLOAD_COMPANY_ID: str(company_id),
            PAYLOAD_DOCUMENT_ID: str(document_id),
            PAYLOAD_DOC_TYPE: doc_type,
            PAYLOAD_FISCAL_YEAR: fiscal_year,
            PAYLOAD_CHUNK_INDEX: chunk.chunk_index,
            PAYLOAD_TOKEN_COUNT: chunk.token_count,
        }
        if fiscal_quarter is not None:
            payload[PAYLOAD_FISCAL_QUARTER] = fiscal_quarter
        if chunk.section_key:
            payload[PAYLOAD_SECTION_KEY] = chunk.section_key
        if chunk.section_title:
            payload[PAYLOAD_SECTION_TITLE] = chunk.section_title
        if filing_date:
            payload[PAYLOAD_FILING_DATE] = filing_date
        if period_end_date:
            payload[PAYLOAD_PERIOD_END_DATE] = period_end_date

        points.append(
            qdrant_models.PointStruct(
                id=vector_id,
                vector=embedding,
                payload=payload,
            )
        )

    # Upsert to Qdrant
    await qdrant.upsert_vectors(company_id, points)

    logger.info(
        "Embeddings upserted to Qdrant",
        vectors_count=len(points),
        company_id=str(company_id),
        document_id=str(document_id),
    )

    return EmbeddingResult(
        vectors_upserted=len(points),
        embedding_model=oai._embedding_model,
        dimensions=oai._embedding_dimensions,
    )
