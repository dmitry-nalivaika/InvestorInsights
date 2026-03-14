# filepath: backend/app/rag/chat_agent.py
"""Company Chat Agent — RAG orchestrator.

Coordinates:
  - Retrieval (semantic search + query expansion)
  - Prompt construction (system prompt + context + history)
  - Streaming LLM completion (Azure OpenAI)
  - Source citation extraction (T407)
  - No-results handling (T411)
  - Out-of-scope refusal (T412)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.clients.openai_client import LLMError, LLMUnavailableError, get_openai_client
from app.config import get_settings
from app.observability.logging import get_logger
from app.rag.prompt_builder import (
    assemble_context,
    build_messages,
    build_system_prompt,
    count_tokens,
    format_history,
)
from app.services.retrieval_service import RetrievalService

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

    from app.clients.openai_client import OpenAIClient
    from app.schemas.chat import RetrievalConfig

logger = get_logger(__name__)

# ── No-results / out-of-scope messages ───────────────────────────

_NO_RESULTS_MESSAGE = (
    "I wasn't able to find relevant information in the available SEC filings "
    "to answer your question. This could mean:\n\n"
    "1. The topic isn't covered in the currently ingested documents\n"
    "2. The question may need to be rephrased for better matching\n"
    "3. Additional filings may need to be uploaded\n\n"
    "Please try rephrasing your question or ensure the relevant filings "
    "have been uploaded and processed."
)

_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(stock\s*price|buy|sell|invest\w*|trade|short)\b", re.IGNORECASE),
    re.compile(r"\b(predict|forecast|will\s+the\s+stock)\b", re.IGNORECASE),
    re.compile(r"\b(personal\s+advice|should\s+i|investment\s+advice)\b", re.IGNORECASE),
    re.compile(r"\b(weather|sports|politics|recipe|joke)\b", re.IGNORECASE),
]

_OUT_OF_SCOPE_REFUSAL = (
    "I'm designed to help you analyze SEC filings and financial data for this company. "
    "I can't provide investment advice, stock price predictions, or answer questions "
    "unrelated to the company's regulatory filings. "
    "Please ask me about the company's financial statements, risk factors, "
    "business operations, or other topics covered in their SEC filings."
)

# ── Citation extraction ──────────────────────────────────────────

_CITATION_PATTERN = re.compile(
    r"\[Source:\s*([^\]]+)\]",
    re.IGNORECASE,
)


def extract_citations(text: str) -> list[dict[str, str]]:
    """Extract [Source: ...] citations from generated text (T407).

    Returns list of {"citation": "10-K 2024, Item 1A"} dicts.
    """
    return [
        {"citation": match.group(1).strip()}
        for match in _CITATION_PATTERN.finditer(text)
    ]


# ── Agent class ──────────────────────────────────────────────────


class CompanyChatAgent:
    """RAG chat agent scoped to a single company.

    Orchestrates retrieval → prompt build → LLM streaming → citation
    extraction for each user turn.
    """

    def __init__(
        self,
        *,
        company_id: uuid.UUID,
        company_name: str,
        ticker: str,
        cik: str | None = None,
        available_doc_types: list[str] | None = None,
        available_years: list[int] | None = None,
        openai_client: OpenAIClient | None = None,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self._company_id = company_id
        self._company_name = company_name
        self._ticker = ticker
        self._cik = cik
        self._available_doc_types = available_doc_types or []
        self._available_years = available_years or []

        settings = get_settings()
        self._openai = openai_client or get_openai_client()
        self._retrieval = retrieval_service or RetrievalService(
            company_id, openai_client=self._openai,
        )
        self._max_context_tokens = settings.rag_max_context_tokens
        self._max_history_tokens = settings.rag_max_history_tokens
        self._max_history_exchanges = settings.rag_max_history_exchanges

        # Build system prompt once (NFR-301: no user input here)
        self._system_prompt = build_system_prompt(
            company_name=company_name,
            ticker=ticker,
            cik=cik,
            available_doc_types=available_doc_types,
            available_years=available_years,
        )

    # ── Main entry point ─────────────────────────────────────────

    async def generate_response(
        self,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
        retrieval_config: RetrievalConfig | None = None,
    ) -> AsyncIterator[ChatAgentEvent]:
        """Generate a streaming response for a user question.

        Yields ChatAgentEvent objects representing different stages:
          - SourcesEvent: Retrieved chunks (sent before streaming starts)
          - TokenEvent: Individual tokens from the LLM
          - DoneEvent: Final message with token count and citations

        Args:
            question: The user's question text.
            history: Previous conversation messages as role/content dicts.
            retrieval_config: Optional retrieval tuning parameters.

        Yields:
            ChatAgentEvent instances.
        """
        history = history or []

        # T412: Check for out-of-scope questions
        if self._is_out_of_scope(question):
            yield SourcesEvent(sources=[])
            yield TokenEvent(token=_OUT_OF_SCOPE_REFUSAL)
            yield DoneEvent(
                full_text=_OUT_OF_SCOPE_REFUSAL,
                token_count=count_tokens(_OUT_OF_SCOPE_REFUSAL),
                citations=[],
                model=self._openai.chat_model,
            )
            return

        # Step 1: Retrieve relevant chunks
        try:
            chunks = await self._retrieval.retrieve(
                question, config=retrieval_config,
            )
        except Exception as exc:
            logger.error(
                "Retrieval failed",
                error=str(exc),
                company_id=str(self._company_id),
            )
            chunks = []

        # T411: Handle no results
        if not chunks:
            yield SourcesEvent(sources=[])
            yield TokenEvent(token=_NO_RESULTS_MESSAGE)
            yield DoneEvent(
                full_text=_NO_RESULTS_MESSAGE,
                token_count=count_tokens(_NO_RESULTS_MESSAGE),
                citations=[],
                model=self._openai.chat_model,
            )
            return

        # Step 2: Emit sources event
        source_dicts = [c.to_source_dict() for c in chunks]
        yield SourcesEvent(sources=source_dicts)

        # Step 3: Assemble context
        context = assemble_context(
            chunks, max_tokens=self._max_context_tokens,
        )

        # Step 4: Format history within budget
        trimmed_history = format_history(
            history,
            max_tokens=self._max_history_tokens,
            max_exchanges=self._max_history_exchanges,
        )

        # Step 5: Build LLM messages
        messages = build_messages(
            system_prompt=self._system_prompt,
            history=trimmed_history,
            context=context,
            user_question=question,
        )

        # Step 6: Stream LLM response
        full_text = ""
        token_count = 0
        model_used = self._openai.chat_model

        try:
            async for chunk in self._openai.chat_completion_stream(messages):
                if chunk.content:
                    full_text += chunk.content
                    token_count += 1  # approximate: 1 chunk ≈ 1 token
                    yield TokenEvent(token=chunk.content)
                if chunk.model:
                    model_used = chunk.model
        except (LLMError, LLMUnavailableError) as exc:
            logger.error(
                "LLM streaming failed",
                error=str(exc),
                company_id=str(self._company_id),
            )
            error_msg = (
                "I encountered an error generating a response. "
                "Please try again in a moment."
            )
            if not full_text:
                yield TokenEvent(token=error_msg)
                full_text = error_msg
            yield DoneEvent(
                full_text=full_text,
                token_count=count_tokens(full_text),
                citations=[],
                model=model_used,
                error=str(exc),
            )
            return

        # Step 7: Extract citations (T407)
        citations = extract_citations(full_text)
        actual_token_count = count_tokens(full_text)

        yield DoneEvent(
            full_text=full_text,
            token_count=actual_token_count,
            citations=citations,
            model=model_used,
        )

    # ── Out-of-scope detection (T412) ────────────────────────────

    @staticmethod
    def _is_out_of_scope(question: str) -> bool:
        """Check if a question is clearly out of scope.

        Uses pattern matching for obvious cases. The system prompt
        also instructs the LLM to refuse borderline out-of-scope
        questions, so this is a first-pass filter.
        """
        return any(pattern.search(question) for pattern in _OUT_OF_SCOPE_PATTERNS)


# ── Event types ──────────────────────────────────────────────────


class ChatAgentEvent:
    """Base class for events yielded by CompanyChatAgent."""

    pass


class SourcesEvent(ChatAgentEvent):
    """Retrieved source chunks."""

    __slots__ = ("sources",)

    def __init__(self, sources: list[dict[str, Any]]) -> None:
        self.sources = sources


class TokenEvent(ChatAgentEvent):
    """A single streamed token."""

    __slots__ = ("token",)

    def __init__(self, token: str) -> None:
        self.token = token


class DoneEvent(ChatAgentEvent):
    """Completion signal with metadata."""

    __slots__ = ("citations", "error", "full_text", "model", "token_count")

    def __init__(
        self,
        *,
        full_text: str,
        token_count: int,
        citations: list[dict[str, str]],
        model: str,
        error: str | None = None,
    ) -> None:
        self.full_text = full_text
        self.token_count = token_count
        self.citations = citations
        self.model = model
        self.error = error
