# filepath: backend/tests/unit/test_log_redaction.py
"""
T813 — Log output review: structlog redaction filter tests.

Validates that sensitive data is properly redacted from log entries
by the ``_redact_sensitive_data`` processor in ``app.observability.logging``.
"""

from __future__ import annotations

import pytest

from app.observability.logging import _REDACTED, _redact_sensitive_data


def _make_event(**kwargs) -> dict:
    """Build a minimal structlog event_dict."""
    return {"event": "test", **kwargs}


def _redact(**kwargs) -> dict:
    """Convenience: run the redaction processor and return the result."""
    return _redact_sensitive_data(None, "info", _make_event(**kwargs))


# ── Key-name based redaction ─────────────────────────────────────


class TestKeyNameRedaction:
    """Values are redacted when the log key matches a sensitive name."""

    @pytest.mark.parametrize(
        "key",
        [
            "api_key",
            "api-key",
            "apikey",
            "x-api-key",
            "password",
            "secret",
            "token",
            "authorization",
            "connection_string",
            "connection-string",
            "connectionstring",
            "azure_openai_api_key",
            "openai_api_key",
            "qdrant_api_key",
            "db_password",
            "redis_password",
            "database_url",
            "azure_storage_connection_string",
            "applicationinsights_connection_string",
        ],
    )
    def test_sensitive_key_redacted(self, key: str):
        result = _redact(**{key: "some-secret-value"})
        assert result[key] == _REDACTED

    def test_case_insensitive_key(self):
        """Key matching is case-insensitive (lowered before lookup)."""
        result = _redact(API_KEY="my-key")
        assert result["API_KEY"] == _REDACTED

    def test_non_sensitive_key_preserved(self):
        result = _redact(company_id="abc-123", ticker="AAPL")
        assert result["company_id"] == "abc-123"
        assert result["ticker"] == "AAPL"

    def test_non_string_values_skipped(self):
        """Non-string values are not redacted (only strings are checked)."""
        result = _redact(count=42, active=True, items=[1, 2, 3])
        assert result["count"] == 42
        assert result["active"] is True
        assert result["items"] == [1, 2, 3]


# ── Value-pattern based redaction ────────────────────────────────


class TestValuePatternRedaction:
    """Values are redacted when their content matches a sensitive pattern."""

    def test_openai_api_key_pattern(self):
        result = _redact(some_field="Bearer sk-abc1234567890123456789xyz")
        assert result["some_field"] == _REDACTED

    def test_azure_connection_string_pattern(self):
        result = _redact(
            config="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=abc123"
        )
        assert result["config"] == _REDACTED

    def test_postgresql_url_with_creds(self):
        result = _redact(
            url="postgresql+asyncpg://user:pass@host:5432/dbname"
        )
        assert result["url"] == _REDACTED

    def test_postgresql_url_without_asyncpg(self):
        result = _redact(url="postgresql://user:pass@host:5432/db")
        assert result["url"] == _REDACTED

    def test_redis_url_with_password(self):
        result = _redact(url="redis://:secretpass@redis-host:6379/0")
        assert result["url"] == _REDACTED

    def test_app_insights_instrumentation_key(self):
        result = _redact(
            conn="InstrumentationKey=12345678-abcd-1234-abcd-1234567890ab"
        )
        assert result["conn"] == _REDACTED

    def test_safe_redis_url_preserved(self):
        """Redis URL without password should not be redacted."""
        result = _redact(url="redis://localhost:6379/0")
        assert result["url"] == "redis://localhost:6379/0"

    def test_safe_string_preserved(self):
        result = _redact(path="/api/v1/companies", method="GET")
        assert result["path"] == "/api/v1/companies"
        assert result["method"] == "GET"


# ── Event field preserved ────────────────────────────────────────


class TestEventFieldPreserved:
    """The 'event' key (log message) is preserved unless it matches a pattern."""

    def test_event_message_preserved(self):
        result = _redact(event="Company created", company_id="123")
        assert result["event"] == "Company created"

    def test_event_with_sensitive_pattern_redacted(self):
        """If someone accidentally puts creds in the event message, redact."""
        result = _redact(event="Connecting to postgresql://user:pass@host/db")
        assert result["event"] == _REDACTED


# ── Mixed scenarios ──────────────────────────────────────────────


class TestMixedScenarios:
    """Multiple fields in one event, some sensitive, some safe."""

    def test_partial_redaction(self):
        result = _redact(
            company_id="abc",
            api_key="secret-123",
            ticker="AAPL",
            db_password="hunter2",
        )
        assert result["company_id"] == "abc"
        assert result["api_key"] == _REDACTED
        assert result["ticker"] == "AAPL"
        assert result["db_password"] == _REDACTED
