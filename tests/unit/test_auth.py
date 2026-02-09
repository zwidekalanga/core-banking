"""Unit tests for authentication (JWT + password hashing)."""

import pytest
from jose import JWTError, jwt

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import get_settings


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "secure-password-123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_hash_is_unique(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token("user-123", "admin", username="admin", email="a@b.com")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["username"] == "admin"
        assert payload["email"] == "a@b.com"
        assert payload["type"] == "access"

    def test_default_username_email(self):
        token = create_access_token("user-123", "viewer")
        payload = decode_token(token)
        assert payload["username"] == ""
        assert payload["email"] == ""

    def test_contains_expiry(self):
        token = create_access_token("user-123", "admin")
        payload = decode_token(token)
        assert "exp" in payload


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token("user-456", "analyst", username="analyst", email="b@c.com")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["role"] == "analyst"
        assert payload["type"] == "refresh"

    def test_different_from_access(self):
        access = create_access_token("user-1", "admin")
        refresh = create_refresh_token("user-1", "admin")
        assert access != refresh

        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"


class TestDecodeToken:
    def test_invalid_token(self):
        with pytest.raises(JWTError):
            decode_token("not-a-valid-token")

    def test_wrong_secret(self):
        settings = get_settings()
        token = jwt.encode(
            {"sub": "user-1", "role": "admin"},
            "wrong-secret",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_expired_token(self):
        from datetime import UTC, datetime, timedelta

        settings = get_settings()
        expired_payload = {
            "sub": "user-1",
            "role": "admin",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(JWTError):
            decode_token(token)


class TestTokenUserDependency:
    """Test the stateless auth dependency logic (without FastAPI context)."""

    def test_access_token_has_all_claims(self):
        token = create_access_token(
            "user-abc", "analyst", username="analyst_user", email="analyst@test.com"
        )
        payload = decode_token(token)
        assert payload["sub"] == "user-abc"
        assert payload["role"] == "analyst"
        assert payload["username"] == "analyst_user"
        assert payload["email"] == "analyst@test.com"
        assert payload["type"] == "access"

    def test_refresh_token_is_not_access(self):
        token = create_refresh_token("user-abc", "admin")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        # The get_current_user dependency should reject this
