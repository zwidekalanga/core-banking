"""Repository for transaction data access."""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.transaction import TransactionFilter
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate


class TransactionRepository:
    """Data access layer for transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, txn_id: str) -> Transaction | None:
        result = await self.session.execute(select(Transaction).where(Transaction.id == txn_id))
        return result.scalar_one_or_none()

    def get_list_query(self, filters: TransactionFilter) -> Select[Any]:
        """Return a filtered + sorted query — pagination handled by the library."""
        query = filters.filter(select(Transaction))
        query = filters.sort(query)
        return query

    def get_by_customer_query(self, customer_id: str) -> Select[Any]:
        """Return a query for transactions belonging to a customer."""
        filters = TransactionFilter(customer_id=customer_id)
        return self.get_list_query(filters)

    def get_by_account_query(self, account_id: str) -> Select[Any]:
        """Return a query for transactions belonging to an account."""
        filters = TransactionFilter(account_id=account_id)
        return self.get_list_query(filters)

    async def create(self, data: TransactionCreate) -> Transaction:
        txn = Transaction(**data.model_dump())
        self.session.add(txn)
        await self.session.flush()
        await self.session.refresh(txn)
        return txn
