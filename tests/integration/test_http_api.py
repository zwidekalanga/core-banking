"""Integration tests for customer, account, and transaction API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from app.dependencies import get_account_repo, get_customer_repo, get_transaction_repo
from app.main import app
from tests.conftest import (
    make_account_model,
    make_account_payload,
    make_customer_model,
    make_customer_payload,
    make_transaction_model,
    make_transaction_payload,
)


def _override_repo(dep_fn, mock_repo):
    """Register a dependency override and return a cleanup function."""
    app.dependency_overrides[dep_fn] = lambda: mock_repo
    return mock_repo


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Customers API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCustomersAPI:
    async def test_list_customers(self, admin_client):
        customers = [make_customer_model(), make_customer_model()]
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=(customers, 2))
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.get("/api/v1/customers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_list_customers_with_filters(self, admin_client):
        customers = [make_customer_model(status="active", tier="premium")]
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=(customers, 1))
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.get("/api/v1/customers?status=active&tier=premium")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_customers_pagination(self, admin_client):
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=([], 0))
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.get("/api/v1/customers?page=2&size=10")
        assert resp.status_code == 200

    async def test_get_customer(self, admin_client):
        customer = make_customer_model()
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=customer)
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.get(f"/api/v1/customers/{customer.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == customer.id

    async def test_get_customer_not_found(self, admin_client):
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=None)
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.get("/api/v1/customers/nonexistent")
        assert resp.status_code == 404

    async def test_create_customer(self, admin_client):
        payload = make_customer_payload()
        customer = make_customer_model(**payload)
        mock = AsyncMock()
        mock.create = AsyncMock(return_value=customer)
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.post("/api/v1/customers", json=payload)
        assert resp.status_code == 201
        assert resp.json()["first_name"] == "Test"

    async def test_update_customer(self, admin_client):
        customer = make_customer_model(tier="premium")
        mock = AsyncMock()
        mock.update = AsyncMock(return_value=customer)
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.put(
            f"/api/v1/customers/{customer.id}",
            json={"tier": "premium"},
        )
        assert resp.status_code == 200
        assert resp.json()["tier"] == "premium"

    async def test_update_customer_not_found(self, admin_client):
        mock = AsyncMock()
        mock.update = AsyncMock(return_value=None)
        _override_repo(get_customer_repo, mock)
        resp = await admin_client.put(
            "/api/v1/customers/nonexistent",
            json={"tier": "premium"},
        )
        assert resp.status_code == 404

    async def test_get_customer_accounts(self, admin_client):
        customer = make_customer_model()
        accounts = [make_account_model(customer_id=customer.id)]

        cust_mock = AsyncMock()
        cust_mock.get_by_id = AsyncMock(return_value=customer)
        _override_repo(get_customer_repo, cust_mock)

        acc_mock = AsyncMock()
        acc_mock.get_by_customer = AsyncMock(return_value=accounts)
        _override_repo(get_account_repo, acc_mock)

        resp = await admin_client.get(f"/api/v1/customers/{customer.id}/accounts")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_get_customer_transactions(self, admin_client):
        customer = make_customer_model()
        txns = [make_transaction_model(customer_id=customer.id)]

        cust_mock = AsyncMock()
        cust_mock.get_by_id = AsyncMock(return_value=customer)
        _override_repo(get_customer_repo, cust_mock)

        txn_mock = AsyncMock()
        txn_mock.get_by_customer = AsyncMock(return_value=(txns, 1))
        _override_repo(get_transaction_repo, txn_mock)

        resp = await admin_client.get(f"/api/v1/customers/{customer.id}/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    async def test_analyst_can_list_customers(self, analyst_client):
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=([], 0))
        _override_repo(get_customer_repo, mock)
        resp = await analyst_client.get("/api/v1/customers")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Accounts API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAccountsAPI:
    async def test_get_account(self, admin_client):
        account = make_account_model()
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=account)
        _override_repo(get_account_repo, mock)
        resp = await admin_client.get(f"/api/v1/accounts/{account.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == account.id

    async def test_get_account_not_found(self, admin_client):
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=None)
        _override_repo(get_account_repo, mock)
        resp = await admin_client.get("/api/v1/accounts/nonexistent")
        assert resp.status_code == 404

    async def test_create_account(self, admin_client):
        payload = make_account_payload()
        account = make_account_model(**payload)
        mock = AsyncMock()
        mock.create = AsyncMock(return_value=account)
        _override_repo(get_account_repo, mock)
        resp = await admin_client.post("/api/v1/accounts", json=payload)
        assert resp.status_code == 201

    async def test_update_account(self, admin_client):
        account = make_account_model(status="frozen")
        mock = AsyncMock()
        mock.update = AsyncMock(return_value=account)
        _override_repo(get_account_repo, mock)
        resp = await admin_client.put(
            f"/api/v1/accounts/{account.id}",
            json={"status": "frozen"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "frozen"

    async def test_get_account_transactions(self, admin_client):
        account = make_account_model()
        txns = [make_transaction_model(account_id=account.id)]

        acc_mock = AsyncMock()
        acc_mock.get_by_id = AsyncMock(return_value=account)
        _override_repo(get_account_repo, acc_mock)

        txn_mock = AsyncMock()
        txn_mock.get_by_account = AsyncMock(return_value=(txns, 1))
        _override_repo(get_transaction_repo, txn_mock)

        resp = await admin_client.get(f"/api/v1/accounts/{account.id}/transactions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# Transactions API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTransactionsAPI:
    async def test_list_transactions(self, admin_client):
        txns = [make_transaction_model(), make_transaction_model()]
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=(txns, 2))
        _override_repo(get_transaction_repo, mock)
        resp = await admin_client.get("/api/v1/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    async def test_list_transactions_with_filters(self, admin_client):
        txns = [make_transaction_model(type="purchase")]
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=(txns, 1))
        _override_repo(get_transaction_repo, mock)
        resp = await admin_client.get("/api/v1/transactions?type=purchase&channel=online")
        assert resp.status_code == 200

    async def test_get_transaction(self, admin_client):
        txn = make_transaction_model()
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=txn)
        _override_repo(get_transaction_repo, mock)
        resp = await admin_client.get(f"/api/v1/transactions/{txn.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == txn.id

    async def test_get_transaction_not_found(self, admin_client):
        mock = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=None)
        _override_repo(get_transaction_repo, mock)
        resp = await admin_client.get("/api/v1/transactions/nonexistent")
        assert resp.status_code == 404

    async def test_create_transaction(self, admin_client):
        payload = make_transaction_payload()
        txn = make_transaction_model(**payload)
        with patch("app.api.v1.transactions.TransactionService") as MockService:
            from app.schemas.transaction import TransactionCreateResponse

            create_resp = TransactionCreateResponse.model_validate(txn)
            MockService.return_value.create_and_evaluate = AsyncMock(return_value=create_resp)
            resp = await admin_client.post("/api/v1/transactions", json=payload)
        assert resp.status_code == 201
        assert resp.json()["external_id"] == payload["external_id"]

    async def test_analyst_can_read_transactions(self, analyst_client):
        mock = AsyncMock()
        mock.get_all = AsyncMock(return_value=([], 0))
        _override_repo(get_transaction_repo, mock)
        resp = await analyst_client.get("/api/v1/transactions")
        assert resp.status_code == 200

    async def test_analyst_cannot_create_transaction(self, analyst_client):
        resp = await analyst_client.post("/api/v1/transactions", json={})
        assert resp.status_code == 403
