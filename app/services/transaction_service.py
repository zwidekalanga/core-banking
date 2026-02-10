"""Service layer for transaction orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.account import Account
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    FraudEvaluationResult,
    TransactionCreate,
    TransactionCreateResponse,
)
from app.services.kafka_producer import publish_transaction
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from aiokafka import AIOKafkaProducer

    from app.grpc.fraud_client import FraudEvaluationClient

logger = get_logger(__name__)


class TransactionService:
    """Orchestrates transaction persistence, fraud evaluation, and event publishing."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        fraud_client: FraudEvaluationClient | None = None,
        kafka_producer: AIOKafkaProducer | None = None,
    ) -> None:
        self._session = session
        self.repo = TransactionRepository(session)
        self.settings = settings
        self._fraud_client = fraud_client
        self._kafka_producer = kafka_producer

    async def create_and_evaluate(self, data: TransactionCreate) -> TransactionCreateResponse:
        """Persist transaction, evaluate fraud via gRPC, publish to Kafka."""
        txn = await self.repo.create(data)

        # 1. Real-time fraud evaluation via gRPC (best-effort)
        fraud_result = await self._evaluate_fraud(txn)

        # 2. Publish to Kafka (best-effort)
        await self._publish_to_kafka(txn)

        response = TransactionCreateResponse.model_validate(txn)
        response.fraud_evaluation = fraud_result
        return response

    async def _evaluate_fraud(self, txn) -> FraudEvaluationResult | None:
        """Call gRPC fraud service. Returns None on failure."""
        if self._fraud_client is None:
            return None
        try:
            grpc_resp = await self._fraud_client.evaluate(
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
            logger.info(
                "Fraud evaluation for %s: score=%s decision=%s",
                txn.external_id,
                grpc_resp.risk_score,
                grpc_resp.decision,
            )
            return FraudEvaluationResult(
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
        except Exception:
            logger.warning("gRPC fraud evaluation failed for %s", txn.external_id, exc_info=True)
            return None

    async def _resolve_account_number(self, account_id: str) -> str | None:
        """Look up the account number for a given account ID."""
        result = await self._session.execute(
            select(Account.account_number).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def _publish_to_kafka(self, txn) -> None:
        """Publish transaction event. Logs warning on failure."""
        if self._kafka_producer is None:
            return
        try:
            account_number = await self._resolve_account_number(txn.account_id)
            await publish_transaction(
                self._kafka_producer,
                {
                    "external_id": txn.external_id,
                    "customer_id": txn.customer_id,
                    "account_id": txn.account_id,
                    "account_number": account_number,
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
                },
            )
        except Exception:
            logger.warning(
                "Failed to publish transaction %s to Kafka", txn.external_id, exc_info=True
            )
