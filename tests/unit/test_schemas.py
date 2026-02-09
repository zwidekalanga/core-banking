"""Unit tests for Pydantic schemas."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.schemas.auth import RefreshRequest, TokenResponse, TokenUser, UserResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerSummary, CustomerUpdate
from app.schemas.transaction import TransactionCreate, TransactionResponse


class TestTokenResponse:
    def test_valid(self):
        t = TokenResponse(access_token="abc", refresh_token="def", expires_in=1800)
        assert t.token_type == "bearer"
        assert t.expires_in == 1800

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            TokenResponse(access_token="abc")  # type: ignore[reportCallIssue]


class TestTokenUser:
    def test_valid(self):
        u = TokenUser(id="123", username="admin", role="admin", email="a@b.com")
        assert u.id == "123"
        assert u.email == "a@b.com"

    def test_email_optional(self):
        u = TokenUser(id="123", username="admin", role="admin")
        assert u.email == ""


class TestRefreshRequest:
    def test_valid(self):
        r = RefreshRequest(refresh_token="some-token")
        assert r.refresh_token == "some-token"


class TestUserResponse:
    def test_valid(self):
        u = UserResponse(id="1", username="admin", email="a@b.com", role="admin")
        assert u.full_name == ""
        assert u.is_active is True

    def test_from_attributes(self):
        assert UserResponse.model_config.get("from_attributes") is True


class TestCustomerCreate:
    def test_valid(self):
        c = CustomerCreate(
            external_id="CUS-001",
            first_name="John",
            last_name="Doe",
            email="john@email.com",
            phone="+27821234567",
            id_number="9001015009087",
            date_of_birth=date(1990, 1, 1),
            onboarded_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert c.kyc_status == "pending"
        assert c.tier == "standard"
        assert c.risk_rating == "low"
        assert c.status == "active"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            CustomerCreate(  # type: ignore[reportCallIssue]
                external_id="CUS-001",
                first_name="John",
                # missing last_name and other required fields
            )

    def test_external_id_min_length(self):
        with pytest.raises(ValidationError):
            CustomerCreate(
                external_id="",
                first_name="John",
                last_name="Doe",
                email="j@e.com",
                phone="+27",
                id_number="90",
                date_of_birth=date(1990, 1, 1),
                onboarded_at=datetime(2024, 1, 1, tzinfo=UTC),
            )


class TestCustomerUpdate:
    def test_all_optional(self):
        c = CustomerUpdate()
        assert c.first_name is None
        assert c.email is None

    def test_partial_update(self):
        c = CustomerUpdate(tier="premium", risk_rating="high")
        assert c.tier == "premium"
        assert c.risk_rating == "high"
        assert c.first_name is None


class TestCustomerResponse:
    def test_from_attributes(self):
        assert CustomerResponse.model_config.get("from_attributes") is True


class TestCustomerSummary:
    def test_valid(self):
        s = CustomerSummary(
            customer_id="123",
            full_name="John Doe",
            tier="premium",
            kyc_status="verified",
            account_age_days=365,
            total_accounts=2,
            total_transactions_30d=15,
            total_spend_30d="25000.00",
            avg_transaction_amount="1666.67",
            risk_rating="medium",
        )
        assert s.total_accounts == 2


class TestAccountCreate:
    def test_valid(self):
        a = AccountCreate(
            customer_id="123",
            account_number="1001234567",
            account_type="cheque",
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert a.currency == "ZAR"
        assert a.balance == Decimal("0.00")
        assert a.status == "active"

    def test_account_number_min_length(self):
        with pytest.raises(ValidationError):
            AccountCreate(
                customer_id="123",
                account_number="",
                account_type="cheque",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )


class TestAccountUpdate:
    def test_all_optional(self):
        a = AccountUpdate()
        assert a.status is None
        assert a.balance is None


class TestAccountResponse:
    def test_from_attributes(self):
        assert AccountResponse.model_config.get("from_attributes") is True


class TestTransactionCreate:
    def test_valid(self):
        t = TransactionCreate(
            external_id="TXN-001",
            account_id="acc-1",
            customer_id="cust-1",
            type="purchase",
            amount=Decimal("150.00"),
            channel="online",
        )
        assert t.currency == "ZAR"
        assert t.country_code == "ZA"
        assert t.merchant_name is None

    def test_amount_must_be_positive(self):
        with pytest.raises(ValidationError):
            TransactionCreate(
                external_id="TXN-002",
                account_id="acc-1",
                customer_id="cust-1",
                type="purchase",
                amount=Decimal("0"),
                channel="online",
            )

    def test_negative_amount(self):
        with pytest.raises(ValidationError):
            TransactionCreate(
                external_id="TXN-003",
                account_id="acc-1",
                customer_id="cust-1",
                type="purchase",
                amount=Decimal("-50.00"),
                channel="online",
            )


class TestTransactionResponse:
    def test_from_attributes(self):
        assert TransactionResponse.model_config.get("from_attributes") is True
