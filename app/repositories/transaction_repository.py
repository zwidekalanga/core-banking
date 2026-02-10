"""Repository for transaction data access."""

from sqlalchemy import func, select
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

    async def get_all(
        self,
        filters: TransactionFilter,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Transaction], int]:
        query = filters.filter(select(Transaction))
        count_query = filters.filter(select(func.count()).select_from(Transaction))

        total = (await self.session.execute(count_query)).scalar() or 0

        query = filters.sort(query)
        query = query.offset((page - 1) * size).limit(size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_by_customer(
        self, customer_id: str, page: int = 1, size: int = 50
    ) -> tuple[list[Transaction], int]:
        filters = TransactionFilter(customer_id=customer_id)
        return await self.get_all(filters, page=page, size=size)

    async def get_by_account(
        self, account_id: str, page: int = 1, size: int = 50
    ) -> tuple[list[Transaction], int]:
        filters = TransactionFilter(account_id=account_id)
        return await self.get_all(filters, page=page, size=size)

    async def create(self, data: TransactionCreate) -> Transaction:
        txn = Transaction(**data.model_dump())
        self.session.add(txn)
        await self.session.flush()
        await self.session.refresh(txn)
        return txn
