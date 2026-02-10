"""Integration tests for health and readiness endpoints."""

import pytest


@pytest.mark.asyncio
class TestHealthEndpoints:
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "core-banking-service"

    async def test_ready_returns_200(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["redis"] == "ok"

    async def test_security_headers_present(self, client):
        resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    async def test_request_id_header(self, client):
        resp = await client.get("/health")
        assert "X-Request-ID" in resp.headers
