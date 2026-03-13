# filepath: backend/tests/integration/test_auth.py
"""
Integration tests for API key authentication enforcement.

Spec reference: testing-strategy.md §3.7 Cross-Cutting — test_auth.py

Validates:
  - Missing X-API-Key → 401
  - Invalid X-API-Key → 401
  - Valid X-API-Key   → 200
  - Health endpoint   → 200 without auth (public)
  - 401 error body matches spec structure

Note:
  Tests hit ``/api/v1/test-protected`` — a lightweight stub registered
  by the integration conftest on the auth-guarded ``api_router``.
  This avoids a dependency on feature routers that aren't built yet.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

# The protected endpoint registered by conftest on the auth-guarded api_router.
PROTECTED = "/api/v1/test-protected"


class TestAuthEnforcement:
    """Tests for the require_api_key dependency on protected routes."""

    # ── 401: missing key ─────────────────────────────────────────

    def test_missing_api_key_returns_401(self, client: TestClient) -> None:
        """GET a protected endpoint without the X-API-Key header → 401."""
        response = client.get(PROTECTED)
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self, client: TestClient) -> None:
        """GET with a wrong X-API-Key → 401."""
        response = client.get(
            PROTECTED,
            headers={"X-API-Key": "totally-wrong-key"},
        )
        assert response.status_code == 401

    # ── 200: valid key ───────────────────────────────────────────

    def test_valid_api_key_grants_access(
        self,
        client: TestClient,
        auth_header: dict[str, str],
    ) -> None:
        """GET with the correct X-API-Key passes auth → 200."""
        response = client.get(PROTECTED, headers=auth_header)
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    # ── Health: public ───────────────────────────────────────────

    def test_health_endpoint_no_auth_required(
        self,
        client: TestClient,
    ) -> None:
        """GET /api/v1/health without X-API-Key → 200 (public).

        The health router is mounted directly on the app (not through
        the authenticated api_router) so it bypasses auth.
        """
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("healthy", "degraded", "unhealthy")

    # ── Error body structure ─────────────────────────────────────

    def test_401_error_body_structure(self, client: TestClient) -> None:
        """Verify the 401 error body matches the spec format.

        Expected shape::

            {
                "detail": {
                    "status": 401,
                    "error": "unauthorized",
                    "message": "<human-readable>"
                }
            }
        """
        # Missing key
        resp_missing = client.get(PROTECTED)
        assert resp_missing.status_code == 401
        body_missing = resp_missing.json()
        detail = body_missing["detail"]
        assert detail["status"] == 401
        assert detail["error"] == "unauthorized"
        assert isinstance(detail["message"], str)
        assert len(detail["message"]) > 0

        # Invalid key
        resp_invalid = client.get(
            PROTECTED,
            headers={"X-API-Key": "bad-key"},
        )
        assert resp_invalid.status_code == 401
        body_invalid = resp_invalid.json()
        detail_inv = body_invalid["detail"]
        assert detail_inv["status"] == 401
        assert detail_inv["error"] == "unauthorized"
        assert "invalid" in detail_inv["message"].lower()
