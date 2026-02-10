"""Shared test fixtures for core-banking."""

import os

# Force test settings before any imports
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/core_banking_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.security import create_access_token
from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on settings between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Fake Redis (drop-in async replacement)
# ---------------------------------------------------------------------------


def _make_fake_redis():
    """Create a fakeredis instance that behaves like redis.asyncio.Redis."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------


def _make_mock_session():
    """Create a mock async DB session.

    Supports ``async with factory() as session`` and readiness probe
    (``SELECT 1``).
    """
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = 1
    session.execute.return_value = result_mock
    session.close = AsyncMock()
    return session


def _make_mock_session_factory():
    """Return a callable that mimics ``async_sessionmaker().__call__()``."""
    mock_session = _make_mock_session()

    class _Factory:
        """Mimic async context manager returned by sessionmaker()."""

        def __call__(self):
            return self

        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return _Factory(), mock_session


# ---------------------------------------------------------------------------
# HTTP client fixture (FastAPI app with mocked infra)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app.

    Infrastructure (DB, Redis) is mocked so tests run without devstack.
    """
    session_factory, _ = _make_mock_session_factory()
    fake_redis = _make_fake_redis()

    app.state.engine = MagicMock()
    app.state.session_factory = session_factory
    app.state.redis = fake_redis
    app.state.fraud_client = MagicMock()
    app.state.kafka_producer = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await fake_redis.aclose()


# ---------------------------------------------------------------------------
# Mock DB session fixture (for direct session testing)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_session():
    """Provide a mock database session."""
    return _make_mock_session()


# ---------------------------------------------------------------------------
# Redis fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def redis_client():
    """Provide a fake Redis client."""
    r = _make_fake_redis()
    yield r
    await r.aclose()


# ---------------------------------------------------------------------------
# Auth helpers — generate JWT tokens directly (no login endpoint needed)
# ---------------------------------------------------------------------------


def _make_token(role: str, username: str) -> str:
    """Create a valid JWT access token for testing."""
    return create_access_token(
        user_id=str(uuid.uuid4()),
        role=role,
        username=username,
        email=f"{username}@test.capitec.co.za",
    )


def _auth_headers(role: str, username: str) -> dict[str, str]:
    """Return Authorization header dict with a valid JWT."""
    token = _make_token(role, username)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def admin_client(client) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client pre-authenticated as admin user."""
    client.headers.update(_auth_headers("admin", "admin"))
    yield client
    client.headers.pop("Authorization", None)


@pytest_asyncio.fixture()
async def analyst_client(client) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client pre-authenticated as analyst user."""
    client.headers.update(_auth_headers("analyst", "analyst"))
    yield client
    client.headers.pop("Authorization", None)


@pytest_asyncio.fixture()
async def viewer_client(client) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client pre-authenticated as viewer user."""
    client.headers.update(_auth_headers("viewer", "viewer"))
    yield client
    client.headers.pop("Authorization", None)


# ---------------------------------------------------------------------------
# Mock ORM model factories
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def make_customer_model(**overrides):
    """Return a SimpleNamespace that looks like a Customer ORM instance."""
    data = {
        "id": str(uuid.uuid4()),
        "external_id": f"CUST-{uuid.uuid4().hex[:8]}",
        "first_name": "Test",
        "last_name": "Customer",
        "id_number": "9001015026082",
        "date_of_birth": datetime(1990, 1, 1, tzinfo=UTC).date(),
        "email": "test@capitec.co.za",
        "phone": "+27821234567",
        "kyc_status": "verified",
        "tier": "standard",
        "segment": None,
        "risk_rating": "low",
        "status": "active",
        "onboarded_at": _NOW,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_account_model(**overrides):
    """Return a SimpleNamespace that looks like an Account ORM instance."""
    data = {
        "id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "account_number": f"10{uuid.uuid4().int % 10**8:08d}",
        "account_type": "cheque",
        "status": "active",
        "balance": Decimal("5000.00"),
        "currency": "ZAR",
        "opened_at": _NOW,
        "closed_at": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_transaction_model(**overrides):
    """Return a SimpleNamespace that looks like a Transaction ORM instance."""
    data = {
        "id": str(uuid.uuid4()),
        "external_id": f"TXN-{uuid.uuid4().hex[:12]}",
        "account_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "type": "purchase",
        "amount": Decimal("150.00"),
        "currency": "ZAR",
        "merchant_name": "Test Store",
        "merchant_category": "retail",
        "channel": "online",
        "country_code": "ZA",
        "ip_address": "41.0.0.1",
        "device_id": "fp-abc123",
        "status": "completed",
        "description": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_admin_user_model(**overrides):
    """Return a SimpleNamespace that looks like an AdminUser ORM instance."""
    data = {
        "id": str(uuid.uuid4()),
        "username": "admin",
        "email": "admin@capitec.co.za",
        "hashed_password": "$2b$12$placeholder",
        "role": "admin",
        "is_active": True,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# Payload factories (dicts for HTTP requests)
# ---------------------------------------------------------------------------


def make_customer_payload(**overrides) -> dict:
    """Build a valid customer creation payload."""
    data = {
        "external_id": f"CUST-{uuid.uuid4().hex[:8]}",
        "first_name": "Test",
        "last_name": "Customer",
        "id_number": "9001015026082",
        "date_of_birth": "1990-01-01",
        "email": "test@capitec.co.za",
        "phone": "+27821234567",
        "onboarded_at": _NOW.isoformat(),
    }
    data.update(overrides)
    return data


def make_account_payload(**overrides) -> dict:
    """Build a valid account creation payload."""
    data = {
        "customer_id": str(uuid.uuid4()),
        "account_number": f"10{uuid.uuid4().int % 10**8:08d}",
        "account_type": "cheque",
        "currency": "ZAR",
        "opened_at": _NOW.isoformat(),
    }
    data.update(overrides)
    return data


def make_transaction_payload(**overrides) -> dict:
    """Build a valid transaction creation payload."""
    data = {
        "external_id": f"TXN-{uuid.uuid4().hex[:12]}",
        "account_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "type": "purchase",
        "amount": "150.00",
        "currency": "ZAR",
        "channel": "online",
        "merchant_name": "Test Store",
        "merchant_category": "retail",
        "country_code": "ZA",
    }
    data.update(overrides)
    return data
