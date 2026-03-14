# filepath: backend/app/rag/prompt_builder.py
"""System prompt construction and context assembly for RAG chat.

Handles:
  - Company-specific system prompt generation (T403)
  - Context assembly within token budget (T404, FR-402)
  - History truncation within token budget (FR-405)

NFR-301: User input MUST never appear in system prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tiktoken

from app.observability.logging import get_logger

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievedChunk

logger = get_logger(__name__)

# ── Token counting ───────────────────────────────────────────────

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a string using cl100k_base encoding."""
    return len(_ENCODING.encode(text))


# ── System prompt template ───────────────────────────────────────

# NFR-301: This template is hardcoded server-side. User input NEVER
# appears in the system prompt.
_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert financial analyst assistant for {company_name} (ticker: {ticker}\
{cik_part}). You have access to SEC filing excerpts provided as context.

**Available Data:**
- Document types: {doc_types}
- Filing years: {filing_years}

**Rules:**
1. Ground ALL answers in the provided filing excerpts. Do NOT speculate or use external knowledge.
2. Cite your sources using [Source: <doc_type> <year>, <section>] format.
3. Be precise with financial figures — quote exact numbers from the filings.
4. When comparing across periods, clearly state which periods you are comparing.
5. Distinguish between stated facts and your analytical interpretation.
6. If the provided context does not contain sufficient information to answer the question, \
say so explicitly — do NOT fabricate information.
7. If the question is unrelated to {company_name}'s SEC filings or financial analysis, \
politely decline and explain your scope is limited to this company's filing data.
8. Handle ambiguous questions by asking for clarification or stating your assumptions.
9. Format financial data in tables when comparing multiple metrics or periods.
10. Use Markdown formatting for readability."""


def build_system_prompt(
    *,
    company_name: str,
    ticker: str,
    cik: str | None = None,
    available_doc_types: list[str] | None = None,
    available_years: list[int] | None = None,
) -> str:
    """Build the company-specific system prompt.

    NFR-301 compliance: only server-controlled metadata is injected.
    User input NEVER appears in this prompt.
    """
    cik_part = f", CIK: {cik}" if cik else ""
    doc_types = ", ".join(available_doc_types) if available_doc_types else "Various SEC filings"
    filing_years = (
        ", ".join(str(y) for y in sorted(available_years))
        if available_years
        else "Various years"
    )

    return _SYSTEM_PROMPT_TEMPLATE.format(
        company_name=company_name,
        ticker=ticker,
        cik_part=cik_part,
        doc_types=doc_types,
        filing_years=filing_years,
    )


# ── Context assembly ─────────────────────────────────────────────


def assemble_context(
    chunks: list[RetrievedChunk],
    *,
    max_tokens: int = 12000,
) -> str:
    """Assemble retrieved chunks into a context string within token budget.

    Chunks are added in score-descending order (already sorted by
    RetrievalService) until the token budget is exhausted.

    Each chunk is labelled with its source metadata for citation.

    Args:
        chunks: Scored chunks from retrieval, sorted by score desc.
        max_tokens: Maximum tokens for the context block (FR-402: 12000).

    Returns:
        Formatted context string with source labels.
    """
    if not chunks:
        return ""

    context_parts: list[str] = []
    tokens_used = 0

    for chunk in chunks:
        # Build the labeled chunk
        label = _format_source_label(chunk)
        chunk_text = f"[{label}]\n{chunk.text}"
        chunk_tokens = count_tokens(chunk_text)

        # Check budget
        if tokens_used + chunk_tokens > max_tokens:
            # If we haven't added anything yet, add a truncated version
            if not context_parts:
                remaining = max_tokens - tokens_used
                if remaining > 50:
                    # Truncate to fit
                    truncated = _truncate_to_tokens(chunk_text, remaining)
                    context_parts.append(truncated)
                    tokens_used += count_tokens(truncated)
            break

        context_parts.append(chunk_text)
        tokens_used += chunk_tokens

    context = "\n\n---\n\n".join(context_parts)

    logger.debug(
        "Context assembled",
        chunks_included=len(context_parts),
        chunks_available=len(chunks),
        tokens_used=tokens_used,
        max_tokens=max_tokens,
    )

    return context


def _format_source_label(chunk: RetrievedChunk) -> str:
    """Build a human-readable source label for a chunk."""
    parts = []
    if chunk.doc_type:
        parts.append(f"Source: {chunk.doc_type}")
    if chunk.fiscal_year:
        parts.append(str(chunk.fiscal_year))
    if chunk.section_title:
        parts.append(chunk.section_title)
    elif chunk.section_key:
        parts.append(chunk.section_key)
    return ", ".join(parts) if parts else "Source: filing excerpt"


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within a token budget."""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODING.decode(tokens[:max_tokens]) + "..."


# ── History formatting ───────────────────────────────────────────


def format_history(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4000,
    max_exchanges: int = 10,
) -> list[dict[str, str]]:
    """Trim conversation history to fit within token and exchange budgets.

    FR-405: 10 exchanges max, 4000 token history budget — whichever
    limit is reached first.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Token budget for history (FR-405: 4000).
        max_exchanges: Max user+assistant pairs (FR-405: 10).

    Returns:
        Trimmed list of message dicts, most recent first priority.
    """
    if not messages:
        return []

    # Cap at max_exchanges * 2 messages (each exchange = user + assistant)
    capped = messages[-(max_exchanges * 2):]

    # Now trim from oldest until within token budget
    tokens_used = sum(count_tokens(m["content"]) for m in capped)

    while capped and tokens_used > max_tokens:
        # Remove oldest message
        removed = capped.pop(0)
        tokens_used -= count_tokens(removed["content"])

    return capped


# ── Full message assembly ────────────────────────────────────────


def build_messages(
    *,
    system_prompt: str,
    history: list[dict[str, str]],
    context: str,
    user_question: str,
) -> list[dict[str, str]]:
    """Build the full message list for the LLM call.

    Prompt construction order (from plan.md):
        [0]     system: {company-specific system prompt}
        [1..N-1] user/assistant: {conversation history}
        [N]     user: {context} + {question}

    NFR-301: User input only in user content, never in system prompt.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    # Add conversation history
    messages.extend(history)

    # Build the final user message with context + question
    if context:
        user_content = (
            "Here are relevant excerpts from SEC filings:\n\n"
            f"{context}\n\n"
            "---\n\n"
            f"Question: {user_question}"
        )
    else:
        user_content = user_question

    messages.append({"role": "user", "content": user_content})

    return messages
