# filepath: backend/app/ingestion/pipeline.py
"""Ingestion pipeline orchestrator.

Coordinates all stages of document processing:
    1. Validate file (magic bytes, size, corruption)
    2. Parse (PDF or HTML text extraction)
    3. Clean text
    4. Split into sections
    5. Chunk sections
    6. Generate embeddings and upsert to Qdrant
    7. Update document status at each stage

This module is called from Celery tasks.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.ingestion.chunker import Chunk, chunk_text, count_tokens
from app.ingestion.parsers.html_parser import extract_text_from_html
from app.ingestion.parsers.pdf_parser import extract_text_from_pdf
from app.ingestion.parsers.text_cleaner import clean_text
from app.ingestion.section_splitter import split_into_sections
from app.models.chunk import DocumentChunk
from app.models.document import DocStatus
from app.models.section import DocumentSection
from app.observability.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.document import Document

logger = get_logger(__name__)


# Magic byte prefixes for file type detection (T213)
_PDF_MAGIC = b"%PDF"
_HTML_PREFIXES = (b"<!DO", b"<htm", b"<HTM", b"<!do", b"<HEA", b"<hea", b"<BOD", b"<bod", b"<?xm", b"<?XM")


class IngestionError(Exception):
    """Raised when ingestion fails at any stage."""

    def __init__(self, message: str, stage: str) -> None:
        self.stage = stage
        super().__init__(message)


class IngestionResult:
    """Result of a completed ingestion pipeline run."""

    __slots__ = (
        "chunks_created", "duration_seconds", "page_count",
        "sections_created", "vectors_upserted",
    )

    def __init__(
        self,
        sections_created: int = 0,
        chunks_created: int = 0,
        vectors_upserted: int = 0,
        page_count: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        self.sections_created = sections_created
        self.chunks_created = chunks_created
        self.vectors_upserted = vectors_upserted
        self.page_count = page_count
        self.duration_seconds = duration_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections_created": self.sections_created,
            "chunks_created": self.chunks_created,
            "vectors_upserted": self.vectors_upserted,
            "page_count": self.page_count,
            "duration_seconds": round(self.duration_seconds, 2),
        }


def detect_file_type(data: bytes) -> str:
    """Detect file type from magic bytes.

    Args:
        data: Raw file bytes.

    Returns:
        "pdf" or "html".

    Raises:
        IngestionError: If file type is unsupported.
    """
    if not data:
        raise IngestionError("File is empty", stage="validation")

    if data[:4].startswith(_PDF_MAGIC):
        return "pdf"

    prefix = data[:4]
    for html_prefix in _HTML_PREFIXES:
        if prefix.startswith(html_prefix):
            return "html"

    # Also check for HTML further into the file (some SEC filings start with whitespace/BOM)
    stripped = data.lstrip()[:10]
    if stripped.startswith((b"<!", b"<h", b"<H")):
        return "html"

    raise IngestionError(
        "Unsupported file type. Only PDF and HTML files are accepted. "
        "File does not match expected magic bytes.",
        stage="validation",
    )


async def run_ingestion_pipeline(
    document: Document,
    session: AsyncSession,
    *,
    chunk_size: int = 768,
    chunk_overlap: int = 128,
) -> IngestionResult:
    """Run the full ingestion pipeline for a document.

    Args:
        document: The Document ORM instance (must have storage_key, doc_type, etc.).
        session: The async database session.
        chunk_size: Target chunk size in tokens.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        IngestionResult with stats.

    Raises:
        IngestionError: On any pipeline failure.
    """
    from app.clients.storage_client import get_storage_client
    from app.db.repositories.document_repo import DocumentRepository
    from app.services.document_service import DocumentService

    start_time = time.monotonic()
    repo = DocumentRepository(session)
    doc_service = DocumentService(session)

    result = IngestionResult()

    try:
        # ── Stage 1: Download file from storage ─────────────────
        logger.info(
            "Ingestion: downloading file",
            document_id=str(document.id),
            storage_key=document.storage_key,
        )
        storage = get_storage_client()
        file_data = await storage.download_blob(document.storage_key)

        # ── Stage 2: Validate file ──────────────────────────────
        file_type = detect_file_type(file_data)

        # ── Stage 3: Transition to PARSING ──────────────────────
        document = await doc_service.transition_status(
            document, DocStatus.PARSING,
        )

        # ── Stage 4: Parse text ─────────────────────────────────
        logger.info(
            "Ingestion: parsing file",
            document_id=str(document.id),
            file_type=file_type,
        )
        if file_type == "pdf":
            parse_result = extract_text_from_pdf(file_data)
            raw_text = parse_result.text
            result.page_count = parse_result.page_count
        else:
            parse_result_html = extract_text_from_html(file_data)
            raw_text = parse_result_html.text
            result.page_count = 0  # HTML doesn't have pages

        if not raw_text.strip():
            raise IngestionError(
                "No text could be extracted from the document",
                stage="parsing",
            )

        # ── Stage 5: Clean text ─────────────────────────────────
        cleaned_text = clean_text(raw_text)

        # ── Stage 6: Split into sections ────────────────────────
        doc_type_val = document.doc_type.value
        sections = split_into_sections(cleaned_text, doc_type_val)

        # ── Stage 7: Save sections to DB ────────────────────────
        logger.info(
            "Ingestion: saving sections",
            document_id=str(document.id),
            section_count=len(sections),
        )
        db_sections: list[DocumentSection] = []
        for section in sections:
            db_section = DocumentSection(
                document_id=document.id,
                section_key=section.key,
                section_title=section.title,
                content_text=section.content,
                char_count=section.char_count,
                token_count=count_tokens(section.content),
            )
            db_sections.append(db_section)

        if db_sections:
            await repo.bulk_create_sections(db_sections)
        result.sections_created = len(db_sections)

        # Transition to PARSED
        document = await doc_service.transition_status(
            document, DocStatus.PARSED,
        )

        # ── Stage 8: Chunk sections ─────────────────────────────
        logger.info(
            "Ingestion: chunking text",
            document_id=str(document.id),
        )
        all_chunks: list[Chunk] = []
        chunk_index = 0
        for section in sections:
            section_chunks = chunk_text(
                section.content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                section_key=section.key,
                section_title=section.title,
                start_index=chunk_index,
            )
            all_chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

        # ── Stage 9: Save chunks to DB ──────────────────────────
        # Build section key → id mapping
        section_id_map: dict[str, Any] = {}
        for db_s in db_sections:
            section_id_map[db_s.section_key] = db_s.id

        db_chunks: list[DocumentChunk] = []
        for chunk in all_chunks:
            db_chunk = DocumentChunk(
                document_id=document.id,
                company_id=document.company_id,
                section_id=section_id_map.get(chunk.section_key) if chunk.section_key else None,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_count=chunk.char_count,
                token_count=chunk.token_count,
            )
            db_chunks.append(db_chunk)

        if db_chunks:
            await repo.bulk_create_chunks(db_chunks)
        result.chunks_created = len(db_chunks)

        # ── Stage 10: Embed and upsert vectors ──────────────────
        document = await doc_service.transition_status(
            document, DocStatus.EMBEDDING,
        )

        logger.info(
            "Ingestion: embedding chunks",
            document_id=str(document.id),
            chunk_count=len(all_chunks),
        )
        from app.ingestion.embedder import embed_and_upsert_chunks

        embed_result = await embed_and_upsert_chunks(
            chunks=all_chunks,
            company_id=document.company_id,
            document_id=document.id,
            doc_type=doc_type_val,
            fiscal_year=document.fiscal_year,
            fiscal_quarter=document.fiscal_quarter,
            filing_date=str(document.filing_date) if document.filing_date else None,
            period_end_date=str(document.period_end_date) if document.period_end_date else None,
        )
        result.vectors_upserted = embed_result.vectors_upserted

        # Update chunk records with vector IDs and embedding model
        # (The vector_id is set in the chunk's metadata in Qdrant,
        #  not tracked back to DB for now — can be added later)

        # ── Stage 11: Transition to READY ────────────────────────
        document = await doc_service.transition_status(
            document, DocStatus.READY,
        )

        # Update page count
        if result.page_count:
            await repo.update(document, page_count=result.page_count)

        duration = time.monotonic() - start_time
        result.duration_seconds = duration

        logger.info(
            "Ingestion pipeline completed",
            document_id=str(document.id),
            sections=result.sections_created,
            chunks=result.chunks_created,
            vectors=result.vectors_upserted,
            duration_s=round(duration, 2),
        )

        return result

    except IngestionError:
        # Re-raise IngestionError as-is
        raise
    except Exception as exc:
        raise IngestionError(
            f"Unexpected error during ingestion: {exc}",
            stage="unknown",
        ) from exc
