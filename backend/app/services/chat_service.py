# filepath: backend/app/services/chat_service.py
"""Chat session and message business logic.

Handles:
  - Session CRUD (T400)
  - Message persistence (T401)
  - Conversation history management (T408)
  - Session title auto-generation (T409)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.middleware.error_handler import NotFoundError
from app.clients.openai_client import LLMError, get_openai_client
from app.config import get_settings
from app.db.repositories.chat_repo import ChatRepository
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.openai_client import OpenAIClient
    from app.models.message import ChatMessage
    from app.models.session import ChatSession

logger = get_logger(__name__)

# ── Title generation prompt ──────────────────────────────────────

_TITLE_SYSTEM_PROMPT = (
    "Generate a short, descriptive title (5-8 words max) for a chat conversation "
    "about SEC filings based on the first user message. "
    "Return ONLY the title text, nothing else. No quotes, no punctuation at the end."
)


class ChatService:
    """Business logic for chat session and message management.

    Each instance is scoped to a single request.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        openai_client: OpenAIClient | None = None,
    ) -> None:
        self._repo = ChatRepository(session)
        self._session = session
        self._openai = openai_client
        self._settings = get_settings()

    @property
    def openai(self) -> OpenAIClient:
        if self._openai is None:
            self._openai = get_openai_client()
        return self._openai

    # ── Session CRUD (T400) ──────────────────────────────────────

    async def create_session(
        self,
        company_id: uuid.UUID,
        *,
        title: str | None = None,
    ) -> ChatSession:
        """Create a new chat session for a company."""
        return await self._repo.create_session(company_id, title=title)

    async def get_session(
        self,
        session_id: uuid.UUID,
        *,
        with_messages: bool = False,
    ) -> ChatSession:
        """Get a session by ID, raising NotFoundError if missing."""
        chat_session = await self._repo.get_session_by_id(
            session_id, with_messages=with_messages,
        )
        if chat_session is None:
            raise NotFoundError("ChatSession", entity_id=str(session_id))
        return chat_session

    async def list_sessions(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        """List chat sessions for a company with pagination."""
        return await self._repo.list_sessions(
            company_id, limit=limit, offset=offset,
        )

    async def delete_session(
        self,
        session_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> None:
        """Delete a chat session, verifying it belongs to the company.

        Raises:
            NotFoundError: If the session doesn't exist or doesn't
                belong to the given company.
        """
        chat_session = await self._repo.get_session_by_id(session_id)
        if chat_session is None or chat_session.company_id != company_id:
            raise NotFoundError("ChatSession", entity_id=str(session_id))
        await self._repo.delete_session(session_id)

    # ── Message persistence (T401) ───────────────────────────────

    async def add_user_message(
        self,
        session_id: uuid.UUID,
        content: str,
    ) -> ChatMessage:
        """Persist a user message."""
        return await self._repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
        )

    async def add_assistant_message(
        self,
        session_id: uuid.UUID,
        content: str,
        *,
        sources: dict[str, Any] | None = None,
        token_count: int | None = None,
        model_used: str | None = None,
    ) -> ChatMessage:
        """Persist an assistant message with optional metadata."""
        return await self._repo.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            sources=sources,
            token_count=token_count,
            model_used=model_used,
        )

    # ── Conversation history (T408) ──────────────────────────────

    async def get_conversation_history(
        self,
        session_id: uuid.UUID,
    ) -> list[dict[str, str]]:
        """Get formatted conversation history for prompt building.

        Returns list of {"role": "user"|"assistant", "content": "..."} dicts.
        Uses the configured max_history_exchanges from settings.
        """
        max_exchanges = self._settings.rag_max_history_exchanges
        messages = await self._repo.get_recent_history(
            session_id, max_exchanges=max_exchanges,
        )
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    # ── Title auto-generation (T409) ─────────────────────────────

    async def auto_generate_title(
        self,
        session_id: uuid.UUID,
        first_message: str,
    ) -> str | None:
        """Generate a title for a new session based on the first message.

        Returns the generated title, or None if generation fails.
        Title generation failures are non-fatal.
        """
        try:
            response = await self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
                    {"role": "user", "content": first_message[:500]},
                ],
                temperature=0.5,
                max_tokens=30,
            )
            title = response.content.strip()[:255]  # Enforce DB column limit
            if title:
                await self._repo.update_session_title(session_id, title)
                logger.debug(
                    "Session title generated",
                    session_id=str(session_id),
                    title=title,
                )
                return title
        except (LLMError, Exception) as exc:
            logger.warning(
                "Title generation failed",
                session_id=str(session_id),
                error=str(exc),
            )
        return None
