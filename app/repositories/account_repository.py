"""Repository for account data access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository:
    """Data access layer for accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, account_id: str) -> Account | None:
        result = await self.session.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def get_by_customer(self, customer_id: str) -> list[Account]:
        result = await self.session.execute(
            select(Account)
            .where(Account.customer_id == customer_id)
            .order_by(Account.opened_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, data: AccountCreate) -> Account:
        account = Account(**data.model_dump())
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(self, account_id: str, data: AccountUpdate) -> Account | None:
        account = await self.get_by_id(account_id)
        if not account:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field, value)

        await self.session.commit()
        await self.session.refresh(account)
        return account
