"""Customer model."""

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class KYCStatus(enum.StrEnum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    expired = "expired"


class CustomerTier(enum.StrEnum):
    standard = "standard"
    premium = "premium"
    private = "private"


class RiskRating(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class CustomerStatus(enum.StrEnum):
    active = "active"
    suspended = "suspended"
    closed = "closed"


class Customer(UUIDMixin, TimestampMixin, Base):
    """Customer record."""

    __tablename__ = "customers"

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    id_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    kyc_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=KYCStatus.pending.value
    )
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CustomerTier.standard.value
    )
    segment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_rating: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RiskRating.low.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CustomerStatus.active.value
    )
    onboarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    accounts = relationship("Account", back_populates="customer", lazy="raise")

    __table_args__ = (
        Index("idx_customer_status", "status"),
        Index("idx_customer_tier", "tier"),
        Index("idx_customer_email", "email", unique=True),
        Index("idx_customer_id_number", "id_number", unique=True),
    )
