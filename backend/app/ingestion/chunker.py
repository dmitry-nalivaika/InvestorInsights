# filepath: backend/app/ingestion/chunker.py
"""Recursive text chunker for document embedding.

Splits text into overlapping chunks of a target token count using
tiktoken for accurate tokenisation. Chunks respect sentence boundaries
where possible.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.observability.logging import get_logger

logger = get_logger(__name__)

# Default tokenizer for text-embedding-3-large
_ENCODING_NAME = "cl100k_base"


@dataclass
class Chunk:
    """A text chunk ready for embedding."""

    content: str
    token_count: int
    char_count: int
    chunk_index: int
    section_key: str | None = None
    section_title: str | None = None


def get_tokenizer(encoding_name: str = _ENCODING_NAME) -> tiktoken.Encoding:
    """Get a cached tiktoken encoding."""
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = _ENCODING_NAME) -> int:
    """Count tokens in a text string."""
    enc = get_tokenizer(encoding_name)
    return len(enc.encode(text))


def chunk_text(
    text: str,
    *,
    chunk_size: int = 768,
    chunk_overlap: int = 128,
    section_key: str | None = None,
    section_title: str | None = None,
    start_index: int = 0,
    encoding_name: str = _ENCODING_NAME,
) -> list[Chunk]:
    """Split text into overlapping chunks of approximately chunk_size tokens.

    Uses a recursive character splitter strategy:
    1. Try splitting on paragraph boundaries (double newline)
    2. Fall back to sentence boundaries (period/question/exclamation)
    3. Fall back to word boundaries (space)
    4. Last resort: character-level split

    Args:
        text: Input text to chunk.
        chunk_size: Target chunk size in tokens.
        chunk_overlap: Number of overlapping tokens between consecutive chunks.
        section_key: Section identifier for metadata.
        section_title: Section title for metadata.
        start_index: Starting chunk index (for multi-section documents).
        encoding_name: Tiktoken encoding name.

    Returns:
        List of Chunk objects.
    """
    if not text.strip():
        return []

    enc = get_tokenizer(encoding_name)
    separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]

    chunks: list[Chunk] = []
    current_index = start_index

    segments = _recursive_split(text, separators, chunk_size, enc)

    # Merge small segments and apply overlap
    merged = _merge_with_overlap(segments, chunk_size, chunk_overlap, enc)

    for segment_text in merged:
        token_count = len(enc.encode(segment_text))
        chunks.append(
            Chunk(
                content=segment_text,
                token_count=token_count,
                char_count=len(segment_text),
                chunk_index=current_index,
                section_key=section_key,
                section_title=section_title,
            )
        )
        current_index += 1

    logger.debug(
        "Text chunked",
        input_length=len(text),
        chunk_count=len(chunks),
        section_key=section_key,
    )

    return chunks


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    enc: tiktoken.Encoding,
) -> list[str]:
    """Recursively split text using the first effective separator."""
    token_count = len(enc.encode(text))
    if token_count <= chunk_size:
        return [text]

    # Try each separator
    for sep in separators:
        if sep == "":
            # Character-level fallback: split by tokens directly
            tokens = enc.encode(text)
            segments = []
            for i in range(0, len(tokens), chunk_size):
                segment = enc.decode(tokens[i : i + chunk_size])
                segments.append(segment)
            return segments

        if sep not in text:
            continue

        parts = text.split(sep)
        segments: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            candidate_tokens = len(enc.encode(candidate))

            if candidate_tokens <= chunk_size:
                current = candidate
            else:
                if current:
                    segments.append(current)
                # If this single part exceeds chunk_size, recurse with next separator
                part_tokens = len(enc.encode(part))
                if part_tokens > chunk_size:
                    remaining_seps = separators[separators.index(sep) + 1 :]
                    sub_segments = _recursive_split(
                        part, remaining_seps, chunk_size, enc,
                    )
                    segments.extend(sub_segments)
                    current = ""
                else:
                    current = part

        if current:
            segments.append(current)

        if segments:
            return segments

    # Shouldn't reach here, but just in case
    return [text]


def _merge_with_overlap(
    segments: list[str],
    chunk_size: int,
    chunk_overlap: int,
    enc: tiktoken.Encoding,
) -> list[str]:
    """Merge segments and add overlap between consecutive chunks."""
    if not segments:
        return []

    if len(segments) == 1:
        return segments

    result: list[str] = []

    for i, segment in enumerate(segments):
        if i == 0:
            result.append(segment)
            continue

        # Get overlap text from the end of the previous segment
        prev_tokens = enc.encode(segments[i - 1])
        if len(prev_tokens) > chunk_overlap:
            overlap_tokens = prev_tokens[-chunk_overlap:]
            overlap_text = enc.decode(overlap_tokens)
        else:
            overlap_text = segments[i - 1]

        # Prepend overlap to current segment
        combined = overlap_text.strip() + " " + segment.strip()
        combined_tokens = len(enc.encode(combined))

        # If combined is too large, just use the segment
        if combined_tokens > chunk_size * 1.2:  # 20% tolerance
            result.append(segment)
        else:
            result.append(combined)

    return result
