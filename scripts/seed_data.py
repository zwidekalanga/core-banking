"""Seed script for core-banking database.

Seeds admin users, demo customers, accounts, and transactions.
Run: python -m scripts.seed_data
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from random import choice, randint, uniform

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.security import hash_password
from app.config import get_settings
from app.models.account import Account
from app.models.admin_user import AdminUser
from app.models.customer import Customer
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)

# ── Admin users ───────────────────────────────────────────────────────────────

ADMIN_USERS = [
    {
        "username": "admin",
        "email": "admin@capitec.co.za",
        "full_name": "System Admin",
        "role": "admin",
        "password": "admin123",
    },
    {
        "username": "analyst",
        "email": "analyst@capitec.co.za",
        "full_name": "Fraud Analyst",
        "role": "analyst",
        "password": "analyst123",
    },
    {
        "username": "viewer",
        "email": "viewer@capitec.co.za",
        "full_name": "Read-only Viewer",
        "role": "viewer",
        "password": "viewer123",
    },
]

# ── Demo customers ────────────────────────────────────────────────────────────

DEMO_CUSTOMERS = [
    {
        "external_id": "CUS-001",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@email.com",
        "phone": "+27821234567",
        "id_number": "9001015009087",
        "date_of_birth": date(1990, 1, 1),
        "kyc_status": "verified",
        "tier": "premium",
        "segment": "young professional",
        "risk_rating": "medium",
        "status": "active",
        "onboarded_at": datetime(2021, 3, 15, tzinfo=timezone.utc),
    },
    {
        "external_id": "CUS-002",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@email.com",
        "phone": "+27829876543",
        "id_number": "8505125009084",
        "date_of_birth": date(1985, 5, 12),
        "kyc_status": "verified",
        "tier": "standard",
        "segment": "family",
        "risk_rating": "low",
        "status": "active",
        "onboarded_at": datetime(2022, 7, 1, tzinfo=timezone.utc),
    },
    {
        "external_id": "CUS-003",
        "first_name": "Thabo",
        "last_name": "Mbeki",
        "email": "thabo.m@email.com",
        "phone": "+27831112233",
        "id_number": "7803065009088",
        "date_of_birth": date(1978, 3, 6),
        "kyc_status": "verified",
        "tier": "private",
        "segment": "high net worth",
        "risk_rating": "low",
        "status": "active",
        "onboarded_at": datetime(2019, 11, 20, tzinfo=timezone.utc),
    },
    {
        "external_id": "CUS-004",
        "first_name": "Nomsa",
        "last_name": "Khumalo",
        "email": "nomsa.k@email.com",
        "phone": "+27844455566",
        "id_number": "9512250009089",
        "date_of_birth": date(1995, 12, 25),
        "kyc_status": "pending",
        "tier": "standard",
        "segment": "student",
        "risk_rating": "low",
        "status": "active",
        "onboarded_at": datetime(2024, 1, 10, tzinfo=timezone.utc),
    },
    {
        "external_id": "CUS-005",
        "first_name": "Pieter",
        "last_name": "van der Merwe",
        "email": "pieter.vdm@email.com",
        "phone": "+27855566677",
        "id_number": "6507085009082",
        "date_of_birth": date(1965, 7, 8),
        "kyc_status": "verified",
        "tier": "premium",
        "segment": "retiree",
        "risk_rating": "high",
        "status": "active",
        "onboarded_at": datetime(2018, 5, 3, tzinfo=timezone.utc),
    },
]

ACCOUNT_TYPES = ["cheque", "savings", "credit", "investment"]
CHANNELS = ["online", "pos", "atm", "mobile", "branch"]
TXN_TYPES = ["purchase", "transfer", "withdrawal", "deposit", "payment"]
MERCHANTS = [
    ("Woolworths", "5411"),
    ("Checkers", "5411"),
    ("Shell Garage", "5541"),
    ("Uber Eats", "5812"),
    ("Netflix", "4899"),
    ("Amazon", "5999"),
    ("Pick n Pay", "5411"),
    ("Takealot", "5999"),
    ("Engen", "5541"),
    ("Mr Price", "5651"),
]


async def seed_admin_users(session: AsyncSession) -> None:
    """Seed admin users if they don't exist."""
    for user_data in ADMIN_USERS:
        existing = await session.execute(
            select(AdminUser).where(AdminUser.username == user_data["username"])
        )
        if existing.scalar_one_or_none():
            logger.info(f"Admin user '{user_data['username']}' already exists, skipping")
            continue

        user = AdminUser(
            id=str(uuid.uuid4()),
            username=user_data["username"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            hashed_password=hash_password(user_data["password"]),
            is_active=True,
        )
        session.add(user)
        logger.info(f"Created admin user: {user_data['username']}")

    await session.commit()


async def seed_customers_and_accounts(session: AsyncSession) -> list[tuple[str, list[str]]]:
    """Seed demo customers and accounts. Returns list of (customer_id, [account_ids])."""
    customer_accounts: list[tuple[str, list[str]]] = []

    for cust_data in DEMO_CUSTOMERS:
        existing = await session.execute(
            select(Customer).where(Customer.external_id == cust_data["external_id"])
        )
        if existing.scalar_one_or_none():
            logger.info(f"Customer '{cust_data['external_id']}' already exists, skipping")
            # Still need to fetch IDs for transactions
            customer = (
                await session.execute(
                    select(Customer).where(Customer.external_id == cust_data["external_id"])
                )
            ).scalar_one()
            accounts = (
                (await session.execute(select(Account).where(Account.customer_id == customer.id)))
                .scalars()
                .all()
            )
            customer_accounts.append((customer.id, [a.id for a in accounts]))
            continue

        customer_id = str(uuid.uuid4())
        customer = Customer(id=customer_id, **cust_data)
        session.add(customer)

        # Create 1-3 accounts per customer
        account_ids = []
        num_accounts = randint(1, 3)
        for i in range(num_accounts):
            account_id = str(uuid.uuid4())
            acct_type = ACCOUNT_TYPES[i % len(ACCOUNT_TYPES)]
            account = Account(
                id=account_id,
                customer_id=customer_id,
                account_number=f"100{randint(1000000, 9999999)}",
                account_type=acct_type,
                currency="ZAR",
                balance=Decimal(str(round(uniform(1000, 500000), 2))),
                status="active",
                opened_at=cust_data["onboarded_at"],
            )
            session.add(account)
            account_ids.append(account_id)

        customer_accounts.append((customer_id, account_ids))
        logger.info(f"Created customer {cust_data['external_id']} with {num_accounts} account(s)")

    await session.commit()
    return customer_accounts


async def seed_transactions(
    session: AsyncSession, customer_accounts: list[tuple[str, list[str]]]
) -> None:
    """Seed demo transactions across all customers."""
    txn_count = 0
    now = datetime.now(timezone.utc)

    for customer_id, account_ids in customer_accounts:
        if not account_ids:
            continue

        # 10-30 transactions per customer over last 60 days
        num_txns = randint(10, 30)
        for _ in range(num_txns):
            account_id = choice(account_ids)
            merchant_name, merchant_category = choice(MERCHANTS)
            days_ago = randint(0, 60)
            txn_time = now - timedelta(days=days_ago, hours=randint(0, 23), minutes=randint(0, 59))

            txn = Transaction(
                id=str(uuid.uuid4()),
                external_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
                account_id=account_id,
                customer_id=customer_id,
                type=choice(TXN_TYPES),
                amount=Decimal(str(round(uniform(10, 25000), 2))),
                currency="ZAR",
                merchant_name=merchant_name,
                merchant_category=merchant_category,
                channel=choice(CHANNELS),
                country_code="ZA",
                ip_address=f"41.{randint(0, 255)}.{randint(0, 255)}.{randint(0, 255)}",
                device_id=f"device-{uuid.uuid4().hex[:6]}",
                status="completed",
                description=f"Payment to {merchant_name}",
                created_at=txn_time,
                updated_at=txn_time,
            )
            session.add(txn)
            txn_count += 1

    await session.commit()
    logger.info(f"Created {txn_count} transactions")


async def main() -> None:
    """Run all seed scripts."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        logger.info("Seeding admin users...")
        await seed_admin_users(session)

        logger.info("Seeding customers and accounts...")
        customer_accounts = await seed_customers_and_accounts(session)

        logger.info("Seeding transactions...")
        await seed_transactions(session, customer_accounts)

    await engine.dispose()
    logger.info("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
