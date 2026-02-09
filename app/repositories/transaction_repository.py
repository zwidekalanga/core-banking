"""Repository for transaction data access."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        customer_id: str | None = None,
        account_id: str | None = None,
        type: str | None = None,
        channel: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Transaction], int]:
        query = select(Transaction)
        count_query = select(func.count()).select_from(Transaction)

        if customer_id:
            query = query.where(Transaction.customer_id == customer_id)
            count_query = count_query.where(Transaction.customer_id == customer_id)
        if account_id:
            query = query.where(Transaction.account_id == account_id)
            count_query = count_query.where(Transaction.account_id == account_id)
        if type:
            query = query.where(Transaction.type == type)
            count_query = count_query.where(Transaction.type == type)
        if channel:
            query = query.where(Transaction.channel == channel)
            count_query = count_query.where(Transaction.channel == channel)
        if from_date:
            query = query.where(Transaction.created_at >= from_date)
            count_query = count_query.where(Transaction.created_at >= from_date)
        if to_date:
            query = query.where(Transaction.created_at <= to_date)
            count_query = count_query.where(Transaction.created_at <= to_date)

        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(Transaction.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_by_customer(
        self, customer_id: str, page: int = 1, size: int = 50
    ) -> tuple[list[Transaction], int]:
        return await self.get_all(customer_id=customer_id, page=page, size=size)

    async def get_by_account(
        self, account_id: str, page: int = 1, size: int = 50
    ) -> tuple[list[Transaction], int]:
        return await self.get_all(account_id=account_id, page=page, size=size)

    async def create(self, data: TransactionCreate) -> Transaction:
        txn = Transaction(**data.model_dump())
        self.session.add(txn)
        await self.session.commit()
        await self.session.refresh(txn)
        return txn
