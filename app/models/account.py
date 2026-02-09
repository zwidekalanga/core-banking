"""Account model."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AccountType(enum.StrEnum):
    cheque = "cheque"
    savings = "savings"
    credit = "credit"
    investment = "investment"
    business = "business"


class AccountStatus(enum.StrEnum):
    active = "active"
    frozen = "frozen"
    dormant = "dormant"
    closed = "closed"


class Account(UUIDMixin, TimestampMixin, Base):
    """Bank account linked to a customer."""

    __tablename__ = "accounts"

    customer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="ZAR", nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AccountStatus.active.value
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", back_populates="accounts")

    __table_args__ = (Index("idx_account_customer_type", "customer_id", "account_type"),)
