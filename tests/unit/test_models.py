"""Unit tests for database models and enums."""

import enum

import pytest

from app.models import (
    Account,
    AccountStatus,
    AccountType,
    AdminUser,
    Base,
    Channel,
    Customer,
    CustomerStatus,
    CustomerTier,
    KYCStatus,
    RiskRating,
    Transaction,
    TransactionStatus,
    TransactionType,
    UserRole,
)


class TestKYCStatus:
    def test_values(self):
        assert KYCStatus.pending.value == "pending"
        assert KYCStatus.verified.value == "verified"
        assert KYCStatus.rejected.value == "rejected"
        assert KYCStatus.expired.value == "expired"

    def test_all_members(self):
        assert len(KYCStatus) == 4


class TestCustomerTier:
    def test_values(self):
        assert CustomerTier.standard.value == "standard"
        assert CustomerTier.premium.value == "premium"
        assert CustomerTier.private.value == "private"

    def test_all_members(self):
        assert len(CustomerTier) == 3


class TestRiskRating:
    def test_values(self):
        assert RiskRating.low.value == "low"
        assert RiskRating.medium.value == "medium"
        assert RiskRating.high.value == "high"

    def test_all_members(self):
        assert len(RiskRating) == 3


class TestCustomerStatus:
    def test_values(self):
        assert CustomerStatus.active.value == "active"
        assert CustomerStatus.suspended.value == "suspended"
        assert CustomerStatus.closed.value == "closed"

    def test_all_members(self):
        assert len(CustomerStatus) == 3


class TestAccountType:
    def test_values(self):
        assert AccountType.cheque.value == "cheque"
        assert AccountType.savings.value == "savings"
        assert AccountType.credit.value == "credit"
        assert AccountType.investment.value == "investment"
        assert AccountType.business.value == "business"

    def test_all_members(self):
        assert len(AccountType) == 5


class TestAccountStatus:
    def test_values(self):
        assert AccountStatus.active.value == "active"
        assert AccountStatus.frozen.value == "frozen"
        assert AccountStatus.dormant.value == "dormant"
        assert AccountStatus.closed.value == "closed"

    def test_all_members(self):
        assert len(AccountStatus) == 4


class TestTransactionType:
    def test_values(self):
        assert TransactionType.purchase.value == "purchase"
        assert TransactionType.transfer.value == "transfer"
        assert TransactionType.withdrawal.value == "withdrawal"
        assert TransactionType.deposit.value == "deposit"
        assert TransactionType.payment.value == "payment"
        assert TransactionType.refund.value == "refund"

    def test_all_members(self):
        assert len(TransactionType) == 6


class TestChannel:
    def test_values(self):
        assert Channel.online.value == "online"
        assert Channel.pos.value == "pos"
        assert Channel.atm.value == "atm"
        assert Channel.mobile.value == "mobile"
        assert Channel.branch.value == "branch"

    def test_all_members(self):
        assert len(Channel) == 5


class TestTransactionStatus:
    def test_values(self):
        assert TransactionStatus.pending.value == "pending"
        assert TransactionStatus.completed.value == "completed"
        assert TransactionStatus.failed.value == "failed"
        assert TransactionStatus.reversed.value == "reversed"

    def test_all_members(self):
        assert len(TransactionStatus) == 4


class TestUserRole:
    def test_values(self):
        assert UserRole.admin.value == "admin"
        assert UserRole.analyst.value == "analyst"
        assert UserRole.viewer.value == "viewer"

    def test_all_members(self):
        assert len(UserRole) == 3


class TestEnumStringBehavior:
    """Verify all enums are str-based for direct comparison."""

    @pytest.mark.parametrize(
        "enum_cls",
        [
            KYCStatus,
            CustomerTier,
            RiskRating,
            CustomerStatus,
            AccountType,
            AccountStatus,
            TransactionType,
            Channel,
            TransactionStatus,
            UserRole,
        ],
    )
    def test_enum_is_str_subclass(self, enum_cls: type[enum.Enum]) -> None:
        for member in enum_cls:
            assert isinstance(member, str)
            assert member == member.value


class TestModelTableNames:
    def test_customer_tablename(self):
        assert Customer.__tablename__ == "customers"

    def test_account_tablename(self):
        assert Account.__tablename__ == "accounts"

    def test_transaction_tablename(self):
        assert Transaction.__tablename__ == "transactions"

    def test_admin_user_tablename(self):
        assert AdminUser.__tablename__ == "admin_users"


class TestBaseMetadata:
    def test_all_tables_registered(self):
        table_names = set(Base.metadata.tables.keys())
        assert "customers" in table_names
        assert "accounts" in table_names
        assert "transactions" in table_names
        assert "admin_users" in table_names
