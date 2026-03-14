# filepath: backend/app/ingestion/parsers/html_parser.py
"""HTML text extraction using BeautifulSoup.

Extracts readable text from SEC filing HTML documents,
stripping tags, scripts, styles, and normalising whitespace.
"""

from __future__ import annotations

from typing import Any

from app.observability.logging import get_logger

logger = get_logger(__name__)


class HTMLParseResult:
    """Result of HTML text extraction."""

    __slots__ = ("text", "title", "metadata")

    def __init__(
        self,
        text: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.title = title
        self.metadata = metadata or {}


def extract_text_from_html(data: bytes, encoding: str = "utf-8") -> HTMLParseResult:
    """Extract readable text from an HTML byte stream.

    Args:
        data: Raw HTML bytes.
        encoding: Character encoding (default utf-8).

    Returns:
        HTMLParseResult with cleaned text.

    Raises:
        ValueError: If the HTML is corrupt or unreadable.
    """
    from bs4 import BeautifulSoup

    try:
        # Try decoding with specified encoding, fallback to latin-1
        try:
            html_str = data.decode(encoding)
        except UnicodeDecodeError:
            html_str = data.decode("latin-1")

        soup = BeautifulSoup(html_str, "lxml")
    except Exception as exc:
        raise ValueError(f"Failed to parse HTML: {exc}") from exc

    # Extract title if present
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "meta", "link", "noscript", "head"]):
        tag.decompose()

    # Convert tables to a simple markdown-like format
    for table in soup.find_all("table"):
        table_text = _table_to_text(table)
        table.replace_with(soup.new_string(table_text))

    # Get text with reasonable spacing
    text = soup.get_text(separator="\n")

    # Clean up excessive whitespace
    import re

    # Normalise blank lines (max 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace on each line
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines)
    # Remove leading/trailing whitespace
    text = text.strip()

    logger.info(
        "HTML text extracted",
        text_length=len(text),
        title=title,
    )

    return HTMLParseResult(text=text, title=title)


def _table_to_text(table) -> str:
    """Convert an HTML table to a simple pipe-delimited text representation."""
    rows: list[str] = []
    for tr in table.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            cell_text = td.get_text(strip=True)
            cells.append(cell_text)
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)
