"""Pydantic schemas for customers."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class CustomerCreate(BaseModel):
    """Request schema for creating a customer."""

    external_id: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str
    phone: str
    id_number: str = Field(min_length=1, max_length=20)
    date_of_birth: date
    kyc_status: str = "pending"
    tier: str = "standard"
    segment: str | None = None
    risk_rating: str = "low"
    status: str = "active"
    onboarded_at: datetime


class CustomerUpdate(BaseModel):
    """Request schema for updating a customer."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    kyc_status: str | None = None
    tier: str | None = None
    segment: str | None = None
    risk_rating: str | None = None
    status: str | None = None


class CustomerResponse(BaseModel):
    """Response schema for a customer."""

    id: str
    external_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    id_number: str
    date_of_birth: date
    kyc_status: str
    tier: str
    segment: str | None
    risk_rating: str
    status: str
    onboarded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerSummary(BaseModel):
    """Aggregated customer stats for the portal alert detail page."""

    customer_id: str
    full_name: str
    tier: str
    kyc_status: str
    account_age_days: int
    total_accounts: int
    total_transactions_30d: int
    total_spend_30d: str
    avg_transaction_amount: str
    risk_rating: str


class CustomerListResponse(PaginatedResponse):
    """Paginated list of customers."""

    items: list[CustomerResponse]
