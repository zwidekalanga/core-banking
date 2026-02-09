"""Transaction model."""

import enum
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class TransactionType(enum.StrEnum):
    purchase = "purchase"
    transfer = "transfer"
    withdrawal = "withdrawal"
    deposit = "deposit"
    payment = "payment"
    refund = "refund"


class Channel(enum.StrEnum):
    online = "online"
    pos = "pos"
    atm = "atm"
    mobile = "mobile"
    branch = "branch"


class TransactionStatus(enum.StrEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    reversed = "reversed"


class Transaction(UUIDMixin, TimestampMixin, Base):
    """Financial transaction."""

    __tablename__ = "transactions"

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="ZAR", nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="ZA", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TransactionStatus.completed.value
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("idx_txn_customer_created", "customer_id", "created_at"),
        Index("idx_txn_account_created", "account_id", "created_at"),
    )
