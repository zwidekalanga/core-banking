"""Pydantic schemas for transactions."""

from datetime import datetime
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, Field, field_serializer

from app.schemas.common import PaginatedResponse


class TransactionCreate(BaseModel):
    """Request schema for creating a transaction."""

    external_id: str = Field(min_length=1, max_length=100)
    account_id: str
    customer_id: str
    type: str
    amount: Decimal = Field(gt=0)
    currency: str = "ZAR"
    merchant_name: str | None = None
    merchant_category: str | None = None
    channel: str
    country_code: str = "ZA"
    ip_address: str | None = None
    device_id: str | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    """Response schema for a transaction."""

    id: str
    external_id: str
    account_id: str
    customer_id: str
    type: str
    amount: Decimal
    currency: str
    merchant_name: str | None
    merchant_category: str | None
    channel: str
    country_code: str
    ip_address: str | IPv4Address | IPv6Address | None
    device_id: str | None
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("ip_address")
    @classmethod
    def serialize_ip(cls, v: str | IPv4Address | IPv6Address | None) -> str | None:
        return str(v) if v is not None else None


class FraudEvaluationResult(BaseModel):
    """Fraud evaluation result returned from the gRPC fraud service."""

    risk_score: int
    decision: str
    decision_tier: str
    decision_tier_description: str
    triggered_rules: list[dict[str, str | int | float]] = Field(default_factory=list)
    processing_time_ms: float
    alert_created: bool
    alert_id: str | None = None


class TransactionCreateResponse(TransactionResponse):
    """Response for transaction creation — includes fraud evaluation."""

    fraud_evaluation: FraudEvaluationResult | None = None


class TransactionListResponse(PaginatedResponse):
    """Paginated list of transactions."""

    items: list[TransactionResponse]
