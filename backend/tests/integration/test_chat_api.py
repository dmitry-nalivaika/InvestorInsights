# filepath: backend/tests/integration/test_chat_api.py
"""Integration tests for Chat/RAG API endpoints (T414).

Tests the full chat flow with mocked LLM, including:
  - SSE streaming endpoint
  - Session CRUD routes
  - Source citations in responses
  - Error handling (no docs, missing company)
"""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("API_KEY", "test-api-key-for-integration-tests")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "fake-azure-openai-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "devstoreaccount1")

from fastapi.testclient import TestClient  # noqa: I001, TC002


# ── Helpers ──────────────────────────────────────────────────────


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None

    for line in raw.split("\n"):
        line = line.rstrip()
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = line[6:]
        elif line == "" and current_event is not None and current_data is not None:
            try:
                parsed = json.loads(current_data)
            except json.JSONDecodeError:
                parsed = current_data
            events.append({"event": current_event, "data": parsed})
            current_event = None
            current_data = None

    return events


# ── Test: Chat SSE endpoint ─────────────────────────────────────


class TestChatSSE:
    """Integration tests for POST /companies/{id}/chat (SSE streaming)."""

    @patch("app.api.chat._validate_company")
    def test_chat_company_not_found(
        self,
        mock_validate: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """Chat with non-existent company returns 404."""
        from app.api.middleware.error_handler import NotFoundError

        fake_id = str(uuid.uuid4())
        mock_validate.side_effect = NotFoundError("Company", entity_id=fake_id)
        resp = client.post(
            f"/api/v1/companies/{fake_id}/chat",
            json={"message": "What is the revenue?"},
            headers=auth_header,
        )
        assert resp.status_code == 404

    @patch("app.api.chat._get_ready_doc_metadata")
    @patch("app.api.chat._validate_company")
    def test_chat_no_ready_documents(
        self,
        mock_validate: MagicMock,
        mock_docs: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """Chat returns 422 when company has no READY documents."""
        company_id = str(uuid.uuid4())
        mock_validate.return_value = {
            "company_name": "Test Corp",
            "ticker": "TST",
            "cik": None,
        }
        mock_docs.return_value = ([], [])

        resp = client.post(
            f"/api/v1/companies/{company_id}/chat",
            json={"message": "What is the revenue?"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    @patch("app.api.chat.CompanyChatAgent")
    @patch("app.api.chat.ChatService")
    @patch("app.api.chat._get_ready_doc_metadata")
    @patch("app.api.chat._validate_company")
    def test_chat_full_sse_flow(
        self,
        mock_validate: MagicMock,
        mock_docs: MagicMock,
        mock_chat_svc_cls: MagicMock,
        mock_agent_cls: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """Full chat SSE flow: session → sources → tokens → done."""
        company_id = str(uuid.uuid4())
        session_id = uuid.uuid4()
        message_id = uuid.uuid4()

        mock_validate.return_value = {
            "company_name": "Apple Inc.",
            "ticker": "AAPL",
            "cik": "0000320193",
        }
        mock_docs.return_value = (["10-K"], [2024])

        # Mock ChatService
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = None
        mock_session.company_id = uuid.UUID(company_id)

        mock_svc = MagicMock()
        mock_svc.create_session = AsyncMock(return_value=mock_session)
        mock_svc.get_session = AsyncMock(return_value=mock_session)
        mock_svc.add_user_message = AsyncMock()
        mock_svc.get_conversation_history = AsyncMock(return_value=[])
        mock_svc.auto_generate_title = AsyncMock(return_value="Revenue Analysis")
        mock_svc.add_assistant_message = AsyncMock(
            return_value=MagicMock(id=message_id),
        )
        mock_chat_svc_cls.return_value = mock_svc

        # Mock CompanyChatAgent to yield SSE events
        from app.rag.chat_agent import DoneEvent, SourcesEvent, TokenEvent

        async def mock_generate(*args, **kwargs):
            yield SourcesEvent(sources=[{
                "chunk_id": "c1",
                "doc_type": "10-K",
                "fiscal_year": 2024,
                "section_key": "item_7",
                "score": 0.92,
            }])
            yield TokenEvent(token="Revenue ")
            yield TokenEvent(token="was ")
            yield TokenEvent(token="$100M.")
            yield DoneEvent(
                full_text="Revenue was $100M.",
                token_count=5,
                citations=[{"citation": "10-K 2024, Item 7"}],
                model="gpt-4o-mini",
            )

        mock_agent = MagicMock()
        mock_agent.generate_response = mock_generate
        mock_agent_cls.return_value = mock_agent

        resp = client.post(
            f"/api/v1/companies/{company_id}/chat",
            json={"message": "What is the revenue?"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = _parse_sse_events(resp.text)

        # Verify event sequence
        event_types = [e["event"] for e in events]
        assert "session" in event_types
        assert "sources" in event_types
        assert "token" in event_types
        assert "done" in event_types

        # Verify session event
        session_evt = next(e for e in events if e["event"] == "session")
        assert session_evt["data"]["session_id"] == str(session_id)

        # Verify sources event
        sources_evt = next(e for e in events if e["event"] == "sources")
        assert len(sources_evt["data"]["sources"]) == 1
        assert sources_evt["data"]["sources"][0]["doc_type"] == "10-K"

        # Verify tokens
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) == 3
        full = "".join(e["data"]["token"] for e in token_events)
        assert full == "Revenue was $100M."

        # Verify done event
        done_evt = next(e for e in events if e["event"] == "done")
        assert done_evt["data"]["token_count"] == 5

    @patch("app.api.chat.CompanyChatAgent")
    @patch("app.api.chat.ChatService")
    @patch("app.api.chat._get_ready_doc_metadata")
    @patch("app.api.chat._validate_company")
    def test_chat_with_existing_session(
        self,
        mock_validate: MagicMock,
        mock_docs: MagicMock,
        mock_chat_svc_cls: MagicMock,
        mock_agent_cls: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """Chat with existing session_id reuses that session."""
        company_id = str(uuid.uuid4())
        session_id = uuid.uuid4()

        mock_validate.return_value = {
            "company_name": "Test Corp",
            "ticker": "TST",
            "cik": None,
        }
        mock_docs.return_value = (["10-K"], [2023])

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = "Previous Chat"
        mock_session.company_id = uuid.UUID(company_id)

        mock_svc = MagicMock()
        mock_svc.get_session = AsyncMock(return_value=mock_session)
        mock_svc.add_user_message = AsyncMock()
        mock_svc.get_conversation_history = AsyncMock(return_value=[
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ])
        mock_svc.auto_generate_title = AsyncMock(return_value=None)
        mock_svc.add_assistant_message = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4()),
        )
        mock_chat_svc_cls.return_value = mock_svc

        from app.rag.chat_agent import DoneEvent, SourcesEvent, TokenEvent

        async def mock_generate(*args, **kwargs):
            yield SourcesEvent(sources=[])
            yield TokenEvent(token="OK")
            yield DoneEvent(
                full_text="OK",
                token_count=1,
                citations=[],
                model="gpt-4o-mini",
            )

        mock_agent = MagicMock()
        mock_agent.generate_response = mock_generate
        mock_agent_cls.return_value = mock_agent

        resp = client.post(
            f"/api/v1/companies/{company_id}/chat",
            json={
                "message": "Follow-up question",
                "session_id": str(session_id),
            },
            headers=auth_header,
        )
        assert resp.status_code == 200

        # Should have called get_session, not create_session
        mock_svc.get_session.assert_called_once()
        mock_svc.create_session.assert_not_called()

    def test_chat_requires_auth(self, client: TestClient) -> None:
        """Chat endpoint requires API key."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/companies/{fake_id}/chat",
            json={"message": "Hello"},
        )
        assert resp.status_code in (401, 403)

    def test_chat_empty_message_rejected(
        self, client: TestClient, auth_header: dict,
    ) -> None:
        """Empty message is rejected by validation."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/companies/{fake_id}/chat",
            json={"message": ""},
            headers=auth_header,
        )
        assert resp.status_code == 422


# ── Test: Session CRUD ───────────────────────────────────────────


class TestSessionCRUD:
    """Integration tests for session list/detail/delete endpoints."""

    @patch("app.api.chat._validate_company")
    @patch("app.api.chat.ChatService")
    def test_list_sessions(
        self,
        mock_svc_cls: MagicMock,
        mock_validate: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """GET /sessions returns paginated list."""
        company_id = str(uuid.uuid4())
        mock_validate.return_value = {
            "company_name": "Test Corp",
            "ticker": "TST",
            "cik": None,
        }

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.company_id = uuid.UUID(company_id)
        mock_session.title = "Test Session"
        mock_session.message_count = 3
        mock_session.created_at = now
        mock_session.updated_at = now

        mock_svc = MagicMock()
        mock_svc.list_sessions = AsyncMock(return_value=([mock_session], 1))
        mock_svc_cls.return_value = mock_svc

        resp = client.get(
            f"/api/v1/companies/{company_id}/chat/sessions",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Test Session"

    @patch("app.api.chat._validate_company")
    @patch("app.api.chat.ChatService")
    def test_get_session_detail(
        self,
        mock_svc_cls: MagicMock,
        mock_validate: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """GET /sessions/{id} returns session with messages."""
        company_id = str(uuid.uuid4())
        session_id = uuid.uuid4()

        mock_validate.return_value = {
            "company_name": "Test Corp",
            "ticker": "TST",
            "cik": None,
        }

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        mock_msg = MagicMock()
        mock_msg.id = uuid.uuid4()
        mock_msg.role = "user"
        mock_msg.content = "What is revenue?"
        mock_msg.sources = None
        mock_msg.token_count = None
        mock_msg.model_used = None
        mock_msg.created_at = now

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.company_id = uuid.UUID(company_id)
        mock_session.title = "Revenue Chat"
        mock_session.message_count = 1
        mock_session.created_at = now
        mock_session.updated_at = now
        mock_session.messages = [mock_msg]

        mock_svc = MagicMock()
        mock_svc.get_session = AsyncMock(return_value=mock_session)
        mock_svc_cls.return_value = mock_svc

        resp = client.get(
            f"/api/v1/companies/{company_id}/chat/sessions/{session_id}",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Revenue Chat"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"

    @patch("app.api.chat.ChatService")
    def test_delete_session(
        self,
        mock_svc_cls: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """DELETE /sessions/{id} returns 204."""
        company_id = str(uuid.uuid4())
        session_id = uuid.uuid4()

        mock_svc = MagicMock()
        mock_svc.delete_session = AsyncMock()
        mock_svc_cls.return_value = mock_svc

        resp = client.delete(
            f"/api/v1/companies/{company_id}/chat/sessions/{session_id}",
            headers=auth_header,
        )
        assert resp.status_code == 204

    @patch("app.api.chat._validate_company")
    @patch("app.api.chat.ChatService")
    def test_list_sessions_pagination(
        self,
        mock_svc_cls: MagicMock,
        mock_validate: MagicMock,
        client: TestClient,
        auth_header: dict,
    ) -> None:
        """Session list supports limit/offset pagination."""
        company_id = str(uuid.uuid4())
        mock_validate.return_value = {
            "company_name": "Test Corp",
            "ticker": "TST",
            "cik": None,
        }

        mock_svc = MagicMock()
        mock_svc.list_sessions = AsyncMock(return_value=([], 0))
        mock_svc_cls.return_value = mock_svc

        resp = client.get(
            f"/api/v1/companies/{company_id}/chat/sessions?limit=5&offset=10",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_list_sessions_requires_auth(self, client: TestClient) -> None:
        """Session list requires API key."""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/companies/{fake_id}/chat/sessions")
        assert resp.status_code in (401, 403)
