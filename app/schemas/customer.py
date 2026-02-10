"""Pydantic schemas for customers."""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.customer import CustomerStatus, CustomerTier, KYCStatus, RiskRating
from app.schemas.common import PaginatedResponse


class CustomerCreate(BaseModel):
    """Request schema for creating a customer."""

    external_id: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(pattern=r"^\+27\d{9}$")
    id_number: str = Field(min_length=13, max_length=13, pattern=r"^\d{13}$")
    date_of_birth: date
    kyc_status: KYCStatus = KYCStatus.pending
    tier: CustomerTier = CustomerTier.standard
    segment: str | None = None
    risk_rating: RiskRating = RiskRating.low
    status: CustomerStatus = CustomerStatus.active
    onboarded_at: datetime


class CustomerUpdate(BaseModel):
    """Request schema for updating a customer."""

    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+27\d{9}$")
    kyc_status: KYCStatus | None = None
    tier: CustomerTier | None = None
    segment: str | None = None
    risk_rating: RiskRating | None = None
    status: CustomerStatus | None = None


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
