"""Repository for customer data access."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.customer import CustomerFilter
from app.models.account import Account
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.schemas.customer import CustomerCreate, CustomerSummary, CustomerUpdate


class CustomerRepository:
    """Data access layer for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def get_list_query(self, filters: CustomerFilter) -> Select[Any]:
        """Return a filtered + sorted query — pagination handled by the library."""
        query = filters.filter(select(Customer))
        query = filters.sort(query)
        return query

    async def get_by_id(self, customer_id: str) -> Customer | None:
        result = await self.session.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()

    async def create(self, data: CustomerCreate) -> Customer:
        customer = Customer(**data.model_dump())
        self.session.add(customer)
        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate) -> Customer | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, field, value)

        await self.session.flush()
        await self.session.refresh(customer)
        return customer

    async def get_summary(self, customer_id: str) -> CustomerSummary | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        # Run account lookup and transaction stats concurrently (2 queries, not 3)
        accounts_result, txn_result = await asyncio.gather(
            self.session.execute(
                select(Account.account_number, Account.account_type)
                .where(Account.customer_id == customer_id)
                .order_by(Account.opened_at.asc())
            ),
            self.session.execute(
                select(
                    func.count().label("count"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                    func.coalesce(func.avg(Transaction.amount), 0).label("avg"),
                )
                .where(Transaction.customer_id == customer_id)
                .where(Transaction.created_at >= thirty_days_ago)
            ),
        )

        accounts = accounts_result.all()
        account_count = len(accounts)
        primary_account_number = accounts[0].account_number if accounts else None
        primary_account_type = accounts[0].account_type if accounts else None
        txn_stats = txn_result.one()

        account_age_days = (
            (datetime.now(UTC) - customer.onboarded_at).days if customer.onboarded_at else 0
        )

        return CustomerSummary(
            customer_id=customer.id,
            full_name=f"{customer.first_name} {customer.last_name}",
            tier=customer.tier,
            kyc_status=customer.kyc_status,
            account_age_days=account_age_days,
            total_accounts=account_count,
            total_transactions_30d=int(txn_stats[0]),
            total_spend_30d=f"{txn_stats[1]:.2f}",
            avg_transaction_amount=f"{txn_stats[2]:.2f}",
            risk_rating=customer.risk_rating,
            primary_account_number=primary_account_number,
            primary_account_type=primary_account_type,
        )
