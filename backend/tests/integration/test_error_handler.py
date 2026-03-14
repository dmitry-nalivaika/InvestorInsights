# filepath: backend/tests/integration/test_error_handler.py
"""
Integration tests for the global error handling middleware.

Validates:
  - AppError subclasses produce correct JSON envelope
  - Pydantic validation errors return field-level details
  - Unhandled exceptions return generic 500 (no leak)
  - HTTPException passthrough works (auth 401 already tested in test_auth)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.middleware.error_handler import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# ── Test-only routes that deliberately raise each exception ──────

_error_test_router: APIRouter | None = None


def _get_error_test_router() -> APIRouter:
    """Lazily create a router with error-triggering routes."""
    global _error_test_router
    if _error_test_router is not None:
        return _error_test_router

    router = APIRouter(prefix="/api/v1/test-errors", tags=["test"])

    class StrictBody(BaseModel):
        name: str = Field(..., min_length=1)
        count: int = Field(..., gt=0)

    @router.get("/not-found")
    async def raise_not_found() -> dict:
        raise NotFoundError(entity="Company", entity_id="abc-123")

    @router.get("/conflict")
    async def raise_conflict() -> dict:
        raise ConflictError("Ticker AAPL already exists")

    @router.get("/validation")
    async def raise_validation() -> dict:
        raise ValidationError(
            "Invalid formula expression",
            details=[{"field": "formula", "reason": "Unbalanced parentheses"}],
        )

    @router.get("/external")
    async def raise_external() -> dict:
        raise ExternalServiceError(service="Azure OpenAI")

    @router.get("/rate-limit")
    async def raise_rate_limit() -> dict:
        raise RateLimitError(retry_after=30)

    @router.get("/unhandled")
    async def raise_unhandled() -> dict:
        raise RuntimeError("something broke unexpectedly")

    @router.post("/pydantic-validation")
    async def pydantic_check(body: StrictBody) -> dict:
        return {"ok": True}

    _error_test_router = router
    return router


# ── Tests ────────────────────────────────────────────────────────


class TestErrorHandler:
    """Exercise every error category through the global handler."""

    def test_not_found_error(self, client: TestClient, auth_header: dict) -> None:
        resp = client.get("/api/v1/test-errors/not-found", headers=auth_header)
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == 404
        assert body["error"] == "not_found"
        assert "Company" in body["message"]
        assert "abc-123" in body["message"]

    def test_conflict_error(self, client: TestClient, auth_header: dict) -> None:
        resp = client.get("/api/v1/test-errors/conflict", headers=auth_header)
        assert resp.status_code == 409
        body = resp.json()
        assert body["status"] == 409
        assert body["error"] == "conflict"
        assert "AAPL" in body["message"]

    def test_validation_error(self, client: TestClient, auth_header: dict) -> None:
        resp = client.get("/api/v1/test-errors/validation", headers=auth_header)
        assert resp.status_code == 422
        body = resp.json()
        assert body["status"] == 422
        assert body["error"] == "validation_error"
        assert body["details"] is not None
        assert body["details"][0]["field"] == "formula"

    def test_external_service_error(self, client: TestClient, auth_header: dict) -> None:
        resp = client.get("/api/v1/test-errors/external", headers=auth_header)
        assert resp.status_code == 502
        body = resp.json()
        assert body["status"] == 502
        assert body["error"] == "external_service_error"
        assert "Azure OpenAI" in body["message"]

    def test_rate_limit_error(self, client: TestClient, auth_header: dict) -> None:
        resp = client.get("/api/v1/test-errors/rate-limit", headers=auth_header)
        assert resp.status_code == 429
        body = resp.json()
        assert body["status"] == 429
        assert body["error"] == "rate_limit_exceeded"
        assert resp.headers.get("Retry-After") == "30"

    def test_unhandled_exception_returns_generic_500(
        self, client: TestClient, auth_header: dict
    ) -> None:
        resp = client.get("/api/v1/test-errors/unhandled", headers=auth_header)
        assert resp.status_code == 500
        body = resp.json()
        assert body["status"] == 500
        assert body["error"] == "internal_error"
        # Must NOT leak the actual exception message
        assert "something broke" not in body["message"]
        assert "internal" in body["message"].lower()

    def test_pydantic_validation_returns_field_details(
        self, client: TestClient, auth_header: dict
    ) -> None:
        # Send body with wrong types to trigger per-field validation errors
        resp = client.post(
            "/api/v1/test-errors/pydantic-validation",
            json={"name": 123, "count": "not-a-number"},
            headers=auth_header,
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["status"] == 422
        assert body["error"] == "validation_error"
        assert body["message"] == "Request validation failed"
        assert isinstance(body["details"], list)
        assert len(body["details"]) >= 1
        # Every detail has field + reason
        for detail in body["details"]:
            assert "field" in detail
            assert "reason" in detail

    def test_pydantic_validation_with_wrong_types(
        self, client: TestClient, auth_header: dict
    ) -> None:
        resp = client.post(
            "/api/v1/test-errors/pydantic-validation",
            json={"name": "", "count": -5},
            headers=auth_header,
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"
        assert len(body["details"]) >= 1
