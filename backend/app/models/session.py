# filepath: backend/app/models/session.py
"""ChatSession ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.message import ChatMessage


class ChatSession(UUIDMixin, TimestampMixin, Base):
    """A RAG chat session scoped to a single company."""

    __tablename__ = "chat_sessions"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"),
    )

    # ── Relationships ────────────────────────────────────────────
    company: Mapped[Company] = relationship(
        "Company", back_populates="chat_sessions",
    )
    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan",
        passive_deletes=True, order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.title!r} msgs={self.message_count} id={self.id}>"
