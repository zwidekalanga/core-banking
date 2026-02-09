"""Repository for customer data access."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.schemas.customer import CustomerCreate, CustomerSummary, CustomerUpdate


class CustomerRepository:
    """Data access layer for customers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(
        self,
        status: str | None = None,
        tier: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Customer], int]:
        query = select(Customer)
        count_query = select(func.count()).select_from(Customer)

        if status:
            query = query.where(Customer.status == status)
            count_query = count_query.where(Customer.status == status)
        if tier:
            query = query.where(Customer.tier == tier)
            count_query = count_query.where(Customer.tier == tier)

        total = (await self.session.execute(count_query)).scalar() or 0

        query = query.order_by(Customer.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, customer_id: str) -> Customer | None:
        result = await self.session.execute(select(Customer).where(Customer.id == customer_id))
        return result.scalar_one_or_none()

    async def create(self, data: CustomerCreate) -> Customer:
        customer = Customer(**data.model_dump())
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: str, data: CustomerUpdate) -> Customer | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, field, value)

        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def get_summary(self, customer_id: str) -> CustomerSummary | None:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None

        # Count accounts
        account_count = (
            await self.session.execute(
                select(func.count()).select_from(Account).where(Account.customer_id == customer_id)
            )
        ).scalar() or 0

        # Transaction stats (last 30 days)
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        txn_stats = (
            await self.session.execute(
                select(
                    func.count().label("count"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                    func.coalesce(func.avg(Transaction.amount), 0).label("avg"),
                )
                .where(Transaction.customer_id == customer_id)
                .where(Transaction.created_at >= thirty_days_ago)
            )
        ).one()

        account_age_days = (datetime.now(UTC) - customer.onboarded_at).days

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
        )
