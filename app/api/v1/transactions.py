"""Transaction API endpoints."""

import logging
from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_role
from app.dependencies import DBSession
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    FraudEvaluationResult,
    TransactionCreate,
    TransactionCreateResponse,
    TransactionListResponse,
    TransactionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=TransactionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_transaction(
    data: TransactionCreate,
    db: DBSession,
) -> TransactionCreateResponse:
    """Create a transaction, persist it, evaluate via gRPC, and publish to Kafka."""
    repo = TransactionRepository(db)
    txn = await repo.create(data)

    # 1. Real-time fraud evaluation via gRPC
    fraud_result: FraudEvaluationResult | None = None
    try:
        from app.grpc.fraud_client import get_fraud_client

        client = get_fraud_client()
        grpc_resp = await client.evaluate(
            external_id=txn.external_id,
            customer_id=txn.customer_id,
            amount=float(txn.amount),
            currency=txn.currency,
            transaction_type=txn.type,
            channel=txn.channel,
            merchant_name=txn.merchant_name,
            merchant_category=txn.merchant_category,
            location_country=txn.country_code,
            ip_address=str(txn.ip_address) if txn.ip_address else None,
            device_fingerprint=txn.device_id,
        )
        fraud_result = FraudEvaluationResult(
            risk_score=grpc_resp.risk_score,
            decision=grpc_resp.decision,
            decision_tier=grpc_resp.decision_tier,
            decision_tier_description=grpc_resp.decision_tier_description,
            triggered_rules=[
                {
                    "code": r.code,
                    "name": r.name,
                    "category": r.category,
                    "severity": r.severity,
                    "score": r.score,
                    "description": r.description,
                }
                for r in grpc_resp.triggered_rules
            ],
            processing_time_ms=grpc_resp.processing_time_ms,
            alert_created=grpc_resp.alert_created,
            alert_id=grpc_resp.alert_id or None,
        )
        logger.info(
            f"Fraud evaluation for {txn.external_id}: "
            f"score={grpc_resp.risk_score} decision={grpc_resp.decision}"
        )
    except Exception:
        logger.warning(
            f"gRPC fraud evaluation failed for {txn.external_id}", exc_info=True
        )

    # 2. Publish to Kafka (best-effort — don't fail the request if Kafka is down)
    try:
        from app.services.kafka_producer import publish_transaction

        await publish_transaction(
            {
                "external_id": txn.external_id,
                "customer_id": txn.customer_id,
                "account_id": txn.account_id,
                "amount": str(txn.amount),
                "currency": txn.currency,
                "transaction_type": txn.type,
                "merchant_name": txn.merchant_name,
                "merchant_category": txn.merchant_category,
                "channel": txn.channel,
                "location_country": txn.country_code,
                "ip_address": str(txn.ip_address) if txn.ip_address else None,
                "device_fingerprint": txn.device_id,
                "transaction_time": txn.created_at.isoformat(),
            }
        )
    except Exception:
        logger.warning(
            f"Failed to publish transaction {txn.external_id} to Kafka", exc_info=True
        )

    response = TransactionCreateResponse.model_validate(txn)
    response.fraud_evaluation = fraud_result
    return response


@router.get(
    "/{txn_id}",
    response_model=TransactionResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def get_transaction(
    txn_id: str,
    db: DBSession,
) -> TransactionResponse:
    """Get a transaction by ID."""
    repo = TransactionRepository(db)
    txn = await repo.get_by_id(txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return TransactionResponse.model_validate(txn)


@router.get(
    "",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_role("admin", "analyst"))],
)
async def list_transactions(
    db: DBSession,
    customer_id: str | None = None,
    account_id: str | None = None,
    type: str | None = None,
    channel: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
) -> TransactionListResponse:
    """List transactions with optional filtering and pagination."""
    repo = TransactionRepository(db)
    transactions, total = await repo.get_all(
        customer_id=customer_id,
        account_id=account_id,
        type=type,
        channel=channel,
        from_date=from_date,
        to_date=to_date,
        page=page,
        size=size,
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        size=size,
        pages=ceil(total / size) if total > 0 else 0,
    )
