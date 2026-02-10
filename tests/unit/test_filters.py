"""Unit tests for declarative filter classes."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.filters.customer import CustomerFilter
from app.filters.transaction import TransactionFilter
from app.models.customer import Customer
from app.models.transaction import Transaction


class TestCustomerFilter:
    def test_defaults_are_none(self):
        f = CustomerFilter()
        assert f.status is None
        assert f.tier is None
        assert f.order_by is None

    def test_filter_with_status(self):
        f = CustomerFilter(status="active")
        query = f.filter(select(Customer))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "customers.status" in compiled
        assert "'active'" in compiled

    def test_filter_with_tier(self):
        f = CustomerFilter(tier="premium")
        query = f.filter(select(Customer))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "customers.tier" in compiled
        assert "'premium'" in compiled

    def test_filter_with_both(self):
        f = CustomerFilter(status="active", tier="premium")
        query = f.filter(select(Customer))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "customers.status" in compiled
        assert "customers.tier" in compiled

    def test_no_filter_produces_clean_query(self):
        f = CustomerFilter()
        query = f.filter(select(Customer))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "WHERE" not in compiled


class TestTransactionFilter:
    def test_defaults_are_none(self):
        f = TransactionFilter()
        assert f.customer_id is None
        assert f.account_id is None
        assert f.type is None
        assert f.channel is None
        assert f.created_at__gte is None
        assert f.created_at__lte is None

    def test_filter_by_customer_id(self):
        f = TransactionFilter(customer_id="CUST-001")
        query = f.filter(select(Transaction))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "WHERE" in compiled
        assert "customer_id" in compiled

    def test_filter_by_type_and_channel(self):
        f = TransactionFilter(type="purchase", channel="online")
        query = f.filter(select(Transaction))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "transactions.type" in compiled
        assert "transactions.channel" in compiled

    def test_date_range_filter(self):
        f = TransactionFilter(
            created_at__gte=datetime(2024, 1, 1, tzinfo=timezone.utc),
            created_at__lte=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        query = f.filter(select(Transaction))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "transactions.created_at >=" in compiled
        assert "transactions.created_at <=" in compiled

    def test_no_filter_produces_clean_query(self):
        f = TransactionFilter()
        query = f.filter(select(Transaction))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "WHERE" not in compiled

    def test_partial_filters_only_apply_set_values(self):
        """Only the provided filter field appears in the WHERE clause."""
        f = TransactionFilter(customer_id="CUST-001")
        query = f.filter(select(Transaction))
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        where_clause = compiled.split("WHERE")[1] if "WHERE" in compiled else ""
        assert "customer_id" in where_clause
        assert "channel" not in where_clause
        assert "type" not in where_clause
