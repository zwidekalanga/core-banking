"""Integration tests for authentication endpoints."""

from unittest.mock import AsyncMock

import pytest

from app.auth.security import create_refresh_token, hash_password
from app.dependencies import get_user_repo
from app.main import app
from tests.conftest import make_admin_user_model


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestMeEndpoint:
    async def test_admin_me(self, admin_client):
        resp = await admin_client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"

    async def test_analyst_me(self, analyst_client):
        resp = await analyst_client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "analyst"

    async def test_viewer_me(self, viewer_client):
        resp = await viewer_client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_unauthenticated_me(self, client):
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 401

    async def test_invalid_token_me(self, client):
        client.headers["Authorization"] = "Bearer invalid.token.here"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 401

    async def test_refresh_token_rejected_for_me(self, client):
        """Refresh tokens must not be accepted as access tokens."""
        refresh = create_refresh_token("user-id", "admin", username="admin")
        client.headers["Authorization"] = f"Bearer {refresh}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLoginEndpoint:
    async def test_login_success(self, client):
        user = make_admin_user_model(
            hashed_password=hash_password("admin123"),
        )
        mock = AsyncMock()
        mock.get_by_username = AsyncMock(return_value=user)
        app.dependency_overrides[get_user_repo] = lambda: mock
        resp = await client.post(
            "/api/v1/auth/admin/login",
            data={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        user = make_admin_user_model(
            hashed_password=hash_password("correct_password"),
        )
        mock = AsyncMock()
        mock.get_by_username = AsyncMock(return_value=user)
        app.dependency_overrides[get_user_repo] = lambda: mock
        resp = await client.post(
            "/api/v1/auth/admin/login",
            data={"username": "admin", "password": "wrong_password"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        mock = AsyncMock()
        mock.get_by_username = AsyncMock(return_value=None)
        app.dependency_overrides[get_user_repo] = lambda: mock
        resp = await client.post(
            "/api/v1/auth/admin/login",
            data={"username": "nobody", "password": "pass"},
        )
        assert resp.status_code == 401

    async def test_login_disabled_user(self, client):
        user = make_admin_user_model(
            hashed_password=hash_password("admin123"),
            is_active=False,
        )
        mock = AsyncMock()
        mock.get_by_username = AsyncMock(return_value=user)
        app.dependency_overrides[get_user_repo] = lambda: mock
        resp = await client.post(
            "/api/v1/auth/admin/login",
            data={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestRBACEnforcement:
    async def test_viewer_cannot_create_customer(self, viewer_client):
        resp = await viewer_client.post("/api/v1/customers", json={})
        assert resp.status_code == 403

    async def test_viewer_cannot_create_transaction(self, viewer_client):
        resp = await viewer_client.post("/api/v1/transactions", json={})
        assert resp.status_code == 403

    async def test_analyst_cannot_create_customer(self, analyst_client):
        resp = await analyst_client.post("/api/v1/customers", json={})
        assert resp.status_code == 403

    async def test_analyst_cannot_create_account(self, analyst_client):
        resp = await analyst_client.post("/api/v1/accounts", json={})
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_list_customers(self, client):
        resp = await client.get("/api/v1/customers")
        assert resp.status_code == 401

    async def test_unauthenticated_cannot_list_transactions(self, client):
        resp = await client.get("/api/v1/transactions")
        assert resp.status_code == 401
