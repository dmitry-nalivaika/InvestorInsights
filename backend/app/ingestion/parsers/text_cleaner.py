# filepath: backend/app/ingestion/parsers/text_cleaner.py
"""Text cleaning and normalisation for SEC filings.

Handles Unicode normalisation, whitespace cleanup, header/footer
removal, and other text quality improvements.
"""

from __future__ import annotations

import re
import unicodedata

from app.observability.logging import get_logger

logger = get_logger(__name__)

# Patterns for common SEC filing artifacts
_HEADER_PATTERNS = [
    # Page numbers
    re.compile(r"^\s*-?\s*\d+\s*-?\s*$", re.MULTILINE),
    # "Table of Contents" repeated lines
    re.compile(r"^\s*Table\s+of\s+Contents\s*$", re.MULTILINE | re.IGNORECASE),
    # Common EDGAR footer text
    re.compile(
        r"^\s*(?:EDGAR|Electronic Data Gathering).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

# Patterns for normalisation
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_UNICODE_DASHES = re.compile(r"[\u2013\u2014\u2015]")
_UNICODE_QUOTES = re.compile(r"[\u2018\u2019\u201a\u201b]")
_UNICODE_DOUBLE_QUOTES = re.compile(r"[\u201c\u201d\u201e\u201f]")
_UNICODE_BULLETS = re.compile(r"[\u2022\u2023\u25cf\u25cb\u25e6\u2043]")
_UNICODE_ELLIPSIS = re.compile(r"\u2026")


def clean_text(text: str) -> str:
    """Clean and normalise extracted text from SEC filings.

    Steps:
        1. Unicode normalisation (NFKC)
        2. Replace fancy Unicode characters with ASCII equivalents
        3. Remove common headers/footers
        4. Normalise whitespace
        5. Remove empty lines

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text string.
    """
    if not text:
        return ""

    original_len = len(text)

    # 1. Unicode normalisation
    text = unicodedata.normalize("NFKC", text)

    # 2. Replace fancy characters
    text = _UNICODE_DASHES.sub("-", text)
    text = _UNICODE_QUOTES.sub("'", text)
    text = _UNICODE_DOUBLE_QUOTES.sub('"', text)
    text = _UNICODE_BULLETS.sub("- ", text)
    text = _UNICODE_ELLIPSIS.sub("...", text)

    # Replace non-breaking spaces
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")  # zero-width space
    text = text.replace("\ufeff", "")  # BOM

    # 3. Remove headers/footers
    for pattern in _HEADER_PATTERNS:
        text = pattern.sub("", text)

    # 4. Normalise whitespace
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        # Collapse horizontal whitespace
        line = _MULTI_SPACE.sub(" ", line).strip()
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # 5. Collapse multiple blank lines
    text = _MULTI_NEWLINE.sub("\n\n", text)
    text = text.strip()

    logger.debug(
        "Text cleaned",
        original_length=original_len,
        cleaned_length=len(text),
        reduction_pct=round((1 - len(text) / max(original_len, 1)) * 100, 1),
    )

    return text
