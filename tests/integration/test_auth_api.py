"""Integration tests for authentication endpoints."""

from unittest.mock import AsyncMock

import pytest

from app.auth.security import create_access_token, create_refresh_token, hash_password
from app.dependencies import get_user_repo
from app.main import app
from tests.conftest import make_admin_user_model


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


def _mock_user_repo(user=None):
    """Return a mock UserRepository that returns `user` for get_by_id."""
    mock = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=user)
    app.dependency_overrides[get_user_repo] = lambda: mock
    return mock


@pytest.mark.asyncio
class TestMeEndpoint:
    async def test_admin_me_returns_fresh_db_data(self, client):
        """The /me endpoint should return current data from the DB, not JWT claims."""
        user = make_admin_user_model(
            id="user-123",
            username="admin",
            role="admin",
            full_name="Admin User",
            email="admin@capitec.co.za",
        )
        _mock_user_repo(user)
        token = create_access_token("user-123", "admin", username="admin", email="admin@capitec.co.za")
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "admin"
        assert body["role"] == "admin"
        assert body["full_name"] == "Admin User"

    async def test_analyst_me(self, client):
        user = make_admin_user_model(id="user-456", role="analyst", username="analyst")
        _mock_user_repo(user)
        token = create_access_token("user-456", "analyst", username="analyst")
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "analyst"

    async def test_viewer_me(self, client):
        user = make_admin_user_model(id="user-789", role="viewer", username="viewer")
        _mock_user_repo(user)
        token = create_access_token("user-789", "viewer", username="viewer")
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_me_inactive_user_rejected(self, client):
        """Inactive users should be rejected even with a valid token."""
        user = make_admin_user_model(id="user-x", is_active=False)
        _mock_user_repo(user)
        token = create_access_token("user-x", "admin", username="admin")
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 401

    async def test_me_deleted_user_rejected(self, client):
        """If user no longer exists in DB, return 401."""
        _mock_user_repo(None)
        token = create_access_token("deleted-user", "admin", username="admin")
        client.headers["Authorization"] = f"Bearer {token}"
        resp = await client.get("/api/v1/auth/admin/me")
        assert resp.status_code == 401

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
