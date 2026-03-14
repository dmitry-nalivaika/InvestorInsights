# filepath: backend/app/api/chat.py
"""Chat API routes with SSE streaming.

Endpoints:
  POST   /api/v1/companies/{company_id}/chat                          — Chat (SSE)
  GET    /api/v1/companies/{company_id}/chat/sessions                  — List sessions
  GET    /api/v1/companies/{company_id}/chat/sessions/{session_id}     — Get session detail
  DELETE /api/v1/companies/{company_id}/chat/sessions/{session_id}     — Delete session
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.middleware.error_handler import NotFoundError, ValidationError
from app.db.repositories.company_repo import CompanyRepository
from app.db.repositories.document_repo import DocumentRepository
from app.dependencies import DbSessionDep  # noqa: TC001 - runtime FastAPI dep
from app.models.document import DocStatus
from app.observability.logging import get_logger
from app.rag.chat_agent import (
    CompanyChatAgent,
    DoneEvent,
    SourcesEvent,
    TokenEvent,
)
from app.schemas.chat import (
    ChatRequest,
    ChatSessionDetail,
    ChatSessionList,
    ChatSessionRead,
    SSEDoneEvent,
    SSEErrorEvent,
    SSESessionEvent,
    SSESourcesEvent,
    SSETokenEvent,
)
from app.services.chat_service import ChatService

logger = get_logger(__name__)

router = APIRouter(prefix="/companies/{company_id}/chat", tags=["chat"])


# ── Helpers ──────────────────────────────────────────────────────


def _sse_event(event: str, data: str) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {data}\n\n"


async def _validate_company(
    db: DbSessionDep,
    company_id: uuid.UUID,
) -> dict:
    """Validate company exists and return its metadata.

    Returns dict with company_name, ticker, cik.
    """
    repo = CompanyRepository(db)
    company = await repo.get_by_id(company_id)
    if company is None:
        raise NotFoundError("Company", entity_id=str(company_id))
    return {
        "company_name": company.name,
        "ticker": company.ticker,
        "cik": company.cik,
    }


async def _get_ready_doc_metadata(
    db: DbSessionDep,
    company_id: uuid.UUID,
) -> tuple[list[str], list[int]]:
    """Get available doc types and years from READY documents."""
    repo = DocumentRepository(db)
    docs, _total = await repo.list_by_company(
        company_id, status=DocStatus.READY.value, limit=100,
    )
    doc_types = sorted({d.doc_type.value for d in docs})
    years = sorted({d.fiscal_year for d in docs if d.fiscal_year})
    return doc_types, years


# ── POST /companies/{company_id}/chat — SSE streaming (T406) ────


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_class=StreamingResponse,
    summary="Send a chat message and receive streaming AI response",
    responses={
        200: {"description": "SSE event stream"},
        400: {"description": "No documents ready for this company"},
        404: {"description": "Company not found"},
    },
)
async def chat(
    company_id: uuid.UUID,
    body: ChatRequest,
    db: DbSessionDep,
) -> StreamingResponse:
    """Send a message and receive a streaming AI response via SSE.

    Creates a new session if session_id is not provided.
    Streams token-by-token via Server-Sent Events (FR-403).
    """
    # Validate company exists
    company_info = await _validate_company(db, company_id)

    # Check that the company has at least one READY document
    doc_types, available_years = await _get_ready_doc_metadata(db, company_id)
    if not doc_types:
        raise ValidationError(
            "No documents are ready for analysis. "
            "Please upload and process documents first.",
        )

    # Get or create session
    chat_svc = ChatService(db)
    is_new_session = body.session_id is None

    if body.session_id:
        session = await chat_svc.get_session(body.session_id)
        if session.company_id != company_id:
            raise NotFoundError("ChatSession", entity_id=str(body.session_id))
    else:
        session = await chat_svc.create_session(company_id)

    session_id = session.id

    # Persist user message
    await chat_svc.add_user_message(session_id, body.message)

    # Get conversation history (excluding the message we just added)
    history = await chat_svc.get_conversation_history(session_id)
    # Remove the last message (the one we just added) from history
    # since it will be the current question
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # Commit the session + user message before streaming
    await db.commit()

    # Build the chat agent
    agent = CompanyChatAgent(
        company_id=company_id,
        company_name=company_info["company_name"],
        ticker=company_info["ticker"],
        cik=company_info["cik"],
        available_doc_types=doc_types,
        available_years=available_years,
    )

    async def _stream_events():
        """Generate SSE events from the chat agent."""
        # Emit session event
        title = session.title
        if is_new_session:
            # Auto-generate title in background (T409)
            # We do this inline for simplicity — title gen is fast
            try:
                svc = ChatService(db)
                generated_title = await svc.auto_generate_title(
                    session_id, body.message,
                )
                if generated_title:
                    title = generated_title
                    await db.commit()
            except Exception as exc:
                logger.warning("Title generation error", error=str(exc))

        yield _sse_event(
            "session",
            SSESessionEvent(session_id=session_id, title=title).model_dump_json(),
        )

        # Stream agent response
        full_text = ""
        token_count = 0
        citations: list[dict] = []
        model_used = ""
        message_id = uuid.uuid4()  # placeholder until we persist

        try:
            async for event in agent.generate_response(
                body.message,
                history=history,
                retrieval_config=body.retrieval_config,
            ):
                if isinstance(event, SourcesEvent):
                    yield _sse_event(
                        "sources",
                        SSESourcesEvent(sources=event.sources).model_dump_json(),
                    )
                elif isinstance(event, TokenEvent):
                    yield _sse_event(
                        "token",
                        SSETokenEvent(token=event.token).model_dump_json(),
                    )
                elif isinstance(event, DoneEvent):
                    full_text = event.full_text
                    token_count = event.token_count
                    citations = event.citations
                    model_used = event.model

        except Exception as exc:
            logger.error("Chat streaming error", error=str(exc))
            yield _sse_event(
                "error",
                SSEErrorEvent(
                    error="streaming_error",
                    message="An error occurred during response generation.",
                ).model_dump_json(),
            )
            return

        # Persist assistant message
        try:
            svc = ChatService(db)
            sources_payload = {
                "citations": citations,
                "chunks": [],  # chunk details already sent via sources event
            }
            assistant_msg = await svc.add_assistant_message(
                session_id,
                full_text,
                sources=sources_payload,
                token_count=token_count,
                model_used=model_used,
            )
            message_id = assistant_msg.id
            await db.commit()
        except Exception as exc:
            logger.error(
                "Failed to persist assistant message",
                error=str(exc),
                session_id=str(session_id),
            )

        # Emit done event
        yield _sse_event(
            "done",
            SSEDoneEvent(
                message_id=message_id,
                token_count=token_count,
            ).model_dump_json(),
        )

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET /companies/{company_id}/chat/sessions (T406a) ───────────


@router.get(
    "/sessions",
    response_model=ChatSessionList,
    summary="List chat sessions for a company",
)
async def list_sessions(
    company_id: uuid.UUID,
    db: DbSessionDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ChatSessionList:
    """List chat sessions with pagination."""
    await _validate_company(db, company_id)
    chat_svc = ChatService(db)
    sessions, total = await chat_svc.list_sessions(
        company_id, limit=limit, offset=offset,
    )
    return ChatSessionList(
        items=[ChatSessionRead.model_validate(s) for s in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /companies/{company_id}/chat/sessions/{session_id} ──────


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetail,
    summary="Get full chat session with messages",
)
async def get_session(
    company_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSessionDep,
) -> ChatSessionDetail:
    """Get a chat session with its full message history."""
    await _validate_company(db, company_id)
    chat_svc = ChatService(db)
    session = await chat_svc.get_session(session_id, with_messages=True)
    if session.company_id != company_id:
        raise NotFoundError("ChatSession", entity_id=str(session_id))
    return ChatSessionDetail.model_validate(session)


# ── DELETE /companies/{company_id}/chat/sessions/{session_id} ───


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session and all its messages",
)
async def delete_session(
    company_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSessionDep,
) -> Response:
    """Delete a chat session and all its messages."""
    chat_svc = ChatService(db)
    await chat_svc.delete_session(session_id, company_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
