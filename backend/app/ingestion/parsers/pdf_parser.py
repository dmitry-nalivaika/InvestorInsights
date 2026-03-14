# filepath: backend/app/ingestion/parsers/pdf_parser.py
"""PDF text extraction using PyMuPDF (fitz).

Extracts text page-by-page from PDF documents, preserving
page boundaries for downstream section splitting.
"""

from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger

logger = get_logger(__name__)


class PDFParseResult:
    """Result of PDF text extraction."""

    __slots__ = ("text", "pages", "page_count", "metadata")

    def __init__(
        self,
        text: str,
        pages: list[str],
        page_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.pages = pages
        self.page_count = page_count
        self.metadata = metadata or {}


def extract_text_from_pdf(data: bytes) -> PDFParseResult:
    """Extract text from a PDF byte stream using PyMuPDF.

    Args:
        data: Raw PDF bytes.

    Returns:
        PDFParseResult with full text and per-page text.

    Raises:
        ValueError: If the PDF is corrupt or unreadable.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ImportError(
            "PyMuPDF (fitz) is required for PDF parsing. "
            "Install it with: pip install PyMuPDF"
        ) from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Failed to open PDF: {exc}") from exc

    pages: list[str] = []
    all_text_parts: list[str] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text("text")
            pages.append(page_text)
            all_text_parts.append(page_text)
    finally:
        doc.close()

    full_text = "\n\n".join(all_text_parts)
    page_count = len(pages)

    logger.info(
        "PDF text extracted",
        page_count=page_count,
        text_length=len(full_text),
    )

    return PDFParseResult(
        text=full_text,
        pages=pages,
        page_count=page_count,
    )
