"""Pydantic schemas for accounts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.account import AccountStatus, AccountType


class AccountCreate(BaseModel):
    """Request schema for creating an account."""

    customer_id: str
    account_number: str = Field(min_length=1, max_length=20)
    account_type: AccountType
    currency: str = "ZAR"
    balance: Decimal = Decimal("0.00")
    status: AccountStatus = AccountStatus.active
    opened_at: datetime


class AccountUpdate(BaseModel):
    """Request schema for updating an account."""

    status: AccountStatus | None = None


class AccountResponse(BaseModel):
    """Response schema for an account."""

    id: str
    customer_id: str
    account_number: str
    account_type: str
    currency: str
    balance: Decimal
    status: str
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
