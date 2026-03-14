# filepath: backend/tests/integration/test_health.py
"""
Integration tests for the health check endpoint.

Spec reference: testing-strategy.md §3.7 Cross-Cutting — test_health.py

Validates:
  - Response shape matches HealthResponse schema
  - All 5 components are present
  - Overall status logic (healthy / degraded / unhealthy)
  - Endpoint is public (no auth required — covered in test_auth.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

HEALTH_URL = "/api/v1/health"

# The 5 component keys the spec requires
REQUIRED_COMPONENTS = {"database", "vector_store", "object_storage", "redis", "llm_api"}


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    # ── Response shape ───────────────────────────────────────────

    def test_health_response_shape(self, client: TestClient) -> None:
        """Response contains status, components, version, uptime_seconds."""
        resp = client.get(HEALTH_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert body["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in body
        assert "version" in body
        assert "uptime_seconds" in body
        assert isinstance(body["uptime_seconds"], int)

    def test_all_required_components_present(self, client: TestClient) -> None:
        """All 5 infrastructure components appear in the response."""
        resp = client.get(HEALTH_URL)
        body = resp.json()
        component_keys = set(body["components"].keys())
        assert REQUIRED_COMPONENTS.issubset(component_keys), (
            f"Missing components: {REQUIRED_COMPONENTS - component_keys}"
        )

    def test_component_shape(self, client: TestClient) -> None:
        """Each component has status and latency_ms fields."""
        resp = client.get(HEALTH_URL)
        body = resp.json()
        for name, comp in body["components"].items():
            assert "status" in comp, f"{name} missing 'status'"
            assert comp["status"] in ("healthy", "unhealthy"), (
                f"{name} has unexpected status: {comp['status']}"
            )
            assert "latency_ms" in comp, f"{name} missing 'latency_ms'"

    # ── Overall status logic ─────────────────────────────────────

    def test_all_healthy_returns_healthy(self, client: TestClient) -> None:
        """When all probes pass → overall status is 'healthy'."""
        healthy_result = ("healthy", 1.0, None)

        with patch("app.api.health._probe_database", new_callable=AsyncMock, return_value=healthy_result), \
             patch("app.api.health._probe_vector_store", new_callable=AsyncMock, return_value=healthy_result), \
             patch("app.api.health._probe_object_storage", new_callable=AsyncMock, return_value=healthy_result), \
             patch("app.api.health._probe_redis", new_callable=AsyncMock, return_value=healthy_result), \
             patch("app.api.health._probe_llm_api", new_callable=AsyncMock, return_value=healthy_result):
            resp = client.get(HEALTH_URL)
            body = resp.json()
            assert body["status"] == "healthy"

    def test_db_down_returns_unhealthy(self, client: TestClient) -> None:
        """When the database probe fails → overall status is 'unhealthy'."""
        healthy = ("healthy", 1.0, None)
        db_down = ("unhealthy", 5000.0, "Connection refused")

        with patch("app.api.health._probe_database", new_callable=AsyncMock, return_value=db_down), \
             patch("app.api.health._probe_vector_store", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_object_storage", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_redis", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_llm_api", new_callable=AsyncMock, return_value=healthy):
            resp = client.get(HEALTH_URL)
            body = resp.json()
            assert body["status"] == "unhealthy"
            assert body["components"]["database"]["status"] == "unhealthy"
            assert body["components"]["database"]["error"] is not None

    def test_non_db_down_returns_degraded(self, client: TestClient) -> None:
        """When a non-DB probe fails but DB is up → overall status is 'degraded'."""
        healthy = ("healthy", 1.0, None)
        qdrant_down = ("unhealthy", 5000.0, "Connection refused")

        with patch("app.api.health._probe_database", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_vector_store", new_callable=AsyncMock, return_value=qdrant_down), \
             patch("app.api.health._probe_object_storage", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_redis", new_callable=AsyncMock, return_value=healthy), \
             patch("app.api.health._probe_llm_api", new_callable=AsyncMock, return_value=healthy):
            resp = client.get(HEALTH_URL)
            body = resp.json()
            assert body["status"] == "degraded"
            assert body["components"]["vector_store"]["status"] == "unhealthy"

    def test_version_matches_settings(self, client: TestClient) -> None:
        """The version field should match the configured app version."""
        from app.config import get_settings
        settings = get_settings()
        resp = client.get(HEALTH_URL)
        body = resp.json()
        assert body["version"] == settings.app_version
