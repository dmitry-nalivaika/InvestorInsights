# filepath: backend/app/db/repositories/chat_repo.py
"""Chat data access layer.

Provides async CRUD operations for ChatSession and ChatMessage models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.observability.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ChatRepository:
    """Async repository for ChatSession and ChatMessage CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Session: Create ──────────────────────────────────────────

    async def create_session(
        self,
        company_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatSession:
        """Create a new chat session."""
        chat_session = ChatSession(company_id=company_id, title=title)
        self._session.add(chat_session)
        await self._session.flush()
        await self._session.refresh(chat_session)
        logger.info(
            "Chat session created",
            session_id=str(chat_session.id),
            company_id=str(company_id),
        )
        return chat_session

    # ── Session: Read ────────────────────────────────────────────

    async def get_session_by_id(
        self,
        session_id: uuid.UUID,
        *,
        with_messages: bool = False,
    ) -> ChatSession | None:
        """Fetch a session by ID, optionally eager-loading messages."""
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        if with_messages:
            stmt = stmt.options(selectinload(ChatSession.messages))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        """List sessions for a company with pagination.

        Returns (sessions, total_count).
        """
        # Count
        count_stmt = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.company_id == company_id)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Fetch
        stmt = (
            select(ChatSession)
            .where(ChatSession.company_id == company_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        sessions = list(result.scalars().all())
        return sessions, total

    # ── Session: Update ──────────────────────────────────────────

    async def update_session_title(
        self,
        session_id: uuid.UUID,
        title: str,
    ) -> None:
        """Update the title of a chat session."""
        stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(title=title)
        )
        await self._session.execute(stmt)

    async def increment_message_count(
        self,
        session_id: uuid.UUID,
        increment: int = 1,
    ) -> None:
        """Atomically increment the session's message_count."""
        stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(message_count=ChatSession.message_count + increment)
        )
        await self._session.execute(stmt)

    # ── Session: Delete ──────────────────────────────────────────

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete a session and all its messages (cascade).

        Returns True if a session was actually deleted.
        """
        stmt = delete(ChatSession).where(ChatSession.id == session_id)
        result = await self._session.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info("Chat session deleted", session_id=str(session_id))
        return deleted

    # ── Messages: Create ─────────────────────────────────────────

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        *,
        sources: dict[str, Any] | None = None,
        token_count: int | None = None,
        model_used: str | None = None,
    ) -> ChatMessage:
        """Persist a chat message and increment the session's message_count."""
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            token_count=token_count,
            model_used=model_used,
        )
        self._session.add(msg)
        await self._session.flush()
        await self._session.refresh(msg)

        # Increment the session counter
        await self.increment_message_count(session_id)

        return msg

    # ── Messages: Read ───────────────────────────────────────────

    async def get_messages(
        self,
        session_id: uuid.UUID,
        *,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        """Get messages for a session, ordered by creation time.

        Args:
            session_id: The chat session ID.
            limit: If set, return only the most recent N messages.
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        if limit is not None:
            # Get the last N messages: subquery for ordering
            # We want ascending final order but last N, so use a subquery.
            inner = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .subquery()
            )
            stmt = (
                select(ChatMessage)
                .join(inner, ChatMessage.id == inner.c.id)
                .order_by(ChatMessage.created_at.asc())
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_history(
        self,
        session_id: uuid.UUID,
        max_exchanges: int = 10,
    ) -> list[ChatMessage]:
        """Get the most recent N exchanges (user+assistant pairs).

        Returns up to max_exchanges * 2 messages, in chronological order.
        """
        return await self.get_messages(
            session_id, limit=max_exchanges * 2,
        )
