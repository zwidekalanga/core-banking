"""Unit tests for repository classes.

Tests verify that repositories correctly delegate to the SQLAlchemy session
(execute, add, flush, refresh) without requiring a real database.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.filters.customer import CustomerFilter
from app.filters.transaction import TransactionFilter
from app.repositories.account_repository import AccountRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.transaction import TransactionCreate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def _scalars_all(items: list):
    """Build a chained mock: result.scalars().all() -> items."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _scalar_one_or_none(item):
    """Build a mock: result.scalar_one_or_none() -> item."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


def _scalar(value):
    """Build a mock: result.scalar() -> value."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_session():
    """Create a fresh AsyncMock session."""
    session = AsyncMock()
    session.add = MagicMock()  # sync method
    return session


# =========================================================================
# CustomerRepository
# =========================================================================


class TestCustomerRepository:
    """Tests for CustomerRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        session = _make_session()
        customer = SimpleNamespace(id="c1", first_name="Alice")
        session.execute.return_value = _scalar_one_or_none(customer)

        repo = CustomerRepository(session)
        result = await repo.get_by_id("c1")

        assert result is customer
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = CustomerRepository(session)
        result = await repo.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_returns_items_and_total(self):
        session = _make_session()
        customers = [SimpleNamespace(id="c1"), SimpleNamespace(id="c2")]

        # First execute -> count query, second -> data query
        session.execute.side_effect = [_scalar(2), _scalars_all(customers)]

        repo = CustomerRepository(session)
        filters = CustomerFilter()
        items, total = await repo.get_all(filters, page=1, size=50)

        assert total == 2
        assert len(items) == 2
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_all_pagination_offset(self):
        session = _make_session()
        session.execute.side_effect = [_scalar(10), _scalars_all([])]

        repo = CustomerRepository(session)
        filters = CustomerFilter()
        await repo.get_all(filters, page=3, size=5)

        # Just verify it ran without error — offset/limit applied to query
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_all_with_filters(self):
        session = _make_session()
        session.execute.side_effect = [_scalar(1), _scalars_all([SimpleNamespace(id="c1")])]

        repo = CustomerRepository(session)
        filters = CustomerFilter(status="active", tier="premium")
        items, total = await repo.get_all(filters, page=1, size=50)

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_create_adds_and_flushes(self):
        session = _make_session()
        repo = CustomerRepository(session)

        data = CustomerCreate(
            external_id="EXT-001",
            first_name="Alice",
            last_name="Smith",
            email="alice@test.co.za",
            phone="+27821111111",
            id_number="9001015026082",
            date_of_birth="1990-01-01",
            onboarded_at=_NOW,
        )
        await repo.create(data)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_applies_partial_fields(self):
        session = _make_session()
        customer = SimpleNamespace(id="c1", first_name="Old", tier="standard")
        session.execute.return_value = _scalar_one_or_none(customer)

        repo = CustomerRepository(session)
        data = CustomerUpdate(first_name="New")
        result = await repo.update("c1", data)

        assert result.first_name == "New"
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = CustomerRepository(session)
        data = CustomerUpdate(first_name="New")
        result = await repo.update("nonexistent", data)

        assert result is None
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_summary_returns_none_when_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = CustomerRepository(session)
        result = await repo.get_summary("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_aggregates(self):
        session = _make_session()
        customer = SimpleNamespace(
            id="c1",
            first_name="Alice",
            last_name="Smith",
            tier="premium",
            kyc_status="verified",
            risk_rating="low",
            onboarded_at=_NOW,
        )

        # execute calls: get_by_id, account count, txn stats
        account_count_result = _scalar(3)
        txn_stats_result = MagicMock()
        txn_stats_result.one.return_value = (15, Decimal("7500.00"), Decimal("500.00"))

        session.execute.side_effect = [
            _scalar_one_or_none(customer),  # get_by_id
            account_count_result,  # account count
            txn_stats_result,  # txn stats
        ]

        repo = CustomerRepository(session)
        summary = await repo.get_summary("c1")

        assert summary is not None
        assert summary.customer_id == "c1"
        assert summary.full_name == "Alice Smith"
        assert summary.total_accounts == 3
        assert summary.total_transactions_30d == 15
        assert summary.total_spend_30d == "7500.00"
        assert summary.avg_transaction_amount == "500.00"


# =========================================================================
# AccountRepository
# =========================================================================


class TestAccountRepository:
    """Tests for AccountRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        session = _make_session()
        account = SimpleNamespace(id="a1", account_type="cheque")
        session.execute.return_value = _scalar_one_or_none(account)

        repo = AccountRepository(session)
        result = await repo.get_by_id("a1")

        assert result is account

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = AccountRepository(session)
        result = await repo.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_customer(self):
        session = _make_session()
        accounts = [SimpleNamespace(id="a1"), SimpleNamespace(id="a2")]
        session.execute.return_value = _scalars_all(accounts)

        repo = AccountRepository(session)
        result = await repo.get_by_customer("cust-1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_customer_empty(self):
        session = _make_session()
        session.execute.return_value = _scalars_all([])

        repo = AccountRepository(session)
        result = await repo.get_by_customer("cust-no-accounts")

        assert result == []

    @pytest.mark.asyncio
    async def test_create_adds_and_flushes(self):
        session = _make_session()
        repo = AccountRepository(session)

        data = AccountCreate(
            customer_id=str(uuid.uuid4()),
            account_number="1012345678",
            account_type="cheque",
            currency="ZAR",
            opened_at=_NOW,
        )
        await repo.create(data)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_applies_fields(self):
        session = _make_session()
        account = SimpleNamespace(id="a1", status="active")
        session.execute.return_value = _scalar_one_or_none(account)

        repo = AccountRepository(session)
        data = AccountUpdate(status="frozen")
        result = await repo.update("a1", data)

        assert result.status == "frozen"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = AccountRepository(session)
        data = AccountUpdate(status="frozen")
        result = await repo.update("nonexistent", data)

        assert result is None
        session.flush.assert_not_awaited()


# =========================================================================
# TransactionRepository
# =========================================================================


class TestTransactionRepository:
    """Tests for TransactionRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        session = _make_session()
        txn = SimpleNamespace(id="t1", type="purchase")
        session.execute.return_value = _scalar_one_or_none(txn)

        repo = TransactionRepository(session)
        result = await repo.get_by_id("t1")

        assert result is txn

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = TransactionRepository(session)
        result = await repo.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_returns_items_and_total(self):
        session = _make_session()
        txns = [SimpleNamespace(id="t1"), SimpleNamespace(id="t2"), SimpleNamespace(id="t3")]
        session.execute.side_effect = [_scalar(3), _scalars_all(txns)]

        repo = TransactionRepository(session)
        filters = TransactionFilter()
        items, total = await repo.get_all(filters, page=1, size=50)

        assert total == 3
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_get_all_with_filters(self):
        session = _make_session()
        session.execute.side_effect = [_scalar(1), _scalars_all([SimpleNamespace(id="t1")])]

        repo = TransactionRepository(session)
        filters = TransactionFilter(type="purchase", channel="online")
        items, total = await repo.get_all(filters, page=1, size=50)

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_get_by_customer_delegates_to_get_all(self):
        session = _make_session()
        txns = [SimpleNamespace(id="t1")]
        session.execute.side_effect = [_scalar(1), _scalars_all(txns)]

        repo = TransactionRepository(session)
        items, total = await repo.get_by_customer("cust-1", page=1, size=10)

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_get_by_account_delegates_to_get_all(self):
        session = _make_session()
        txns = [SimpleNamespace(id="t1"), SimpleNamespace(id="t2")]
        session.execute.side_effect = [_scalar(2), _scalars_all(txns)]

        repo = TransactionRepository(session)
        items, total = await repo.get_by_account("acc-1", page=1, size=10)

        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_create_adds_and_flushes(self):
        session = _make_session()
        repo = TransactionRepository(session)

        data = TransactionCreate(
            external_id="TXN-001",
            account_id=str(uuid.uuid4()),
            customer_id=str(uuid.uuid4()),
            type="purchase",
            amount=Decimal("250.00"),
            currency="ZAR",
            channel="online",
            merchant_name="Test Store",
            merchant_category="retail",
            country_code="ZA",
        )
        await repo.create(data)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_all_empty_result(self):
        session = _make_session()
        session.execute.side_effect = [_scalar(0), _scalars_all([])]

        repo = TransactionRepository(session)
        filters = TransactionFilter()
        items, total = await repo.get_all(filters, page=1, size=50)

        assert total == 0
        assert items == []


# =========================================================================
# UserRepository
# =========================================================================


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_get_by_username_found(self):
        session = _make_session()
        user = SimpleNamespace(id="u1", username="admin", role="admin")
        session.execute.return_value = _scalar_one_or_none(user)

        repo = UserRepository(session)
        result = await repo.get_by_username("admin")

        assert result is user
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = UserRepository(session)
        result = await repo.get_by_username("ghost")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        session = _make_session()
        user = SimpleNamespace(id="u1", username="admin")
        session.execute.return_value = _scalar_one_or_none(user)

        repo = UserRepository(session)
        result = await repo.get_by_id("u1")

        assert result is user

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none(None)

        repo = UserRepository(session)
        result = await repo.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_adds_and_flushes(self):
        session = _make_session()
        user = SimpleNamespace(
            id=str(uuid.uuid4()),
            username="newuser",
            email="new@test.co.za",
            hashed_password="$2b$12$hash",
            full_name="New User",
            role="viewer",
            is_active=True,
        )

        repo = UserRepository(session)
        await repo.create(user)

        session.add.assert_called_once_with(user)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(user)
