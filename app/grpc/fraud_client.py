"""Async gRPC client for calling the Fraud Evaluation service."""

import grpc.aio

from app.grpc.generated import fraud_evaluation_pb2, fraud_evaluation_pb2_grpc
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FraudEvaluationClient:
    """Async wrapper around the gRPC FraudEvaluationService stub."""

    def __init__(self, target: str):
        self._target = target
        self._channel: grpc.aio.Channel | None = None
        self._stub: fraud_evaluation_pb2_grpc.FraudEvaluationServiceStub | None = None

    def _get_stub(self) -> fraud_evaluation_pb2_grpc.FraudEvaluationServiceStub:
        if self._stub is None:
            self._channel = grpc.aio.insecure_channel(self._target)
            self._stub = fraud_evaluation_pb2_grpc.FraudEvaluationServiceStub(self._channel)
        return self._stub

    async def evaluate(
        self,
        *,
        external_id: str,
        customer_id: str,
        amount: float,
        currency: str = "ZAR",
        transaction_type: str,
        channel: str,
        merchant_name: str | None = None,
        merchant_category: str | None = None,
        location_country: str | None = None,
        ip_address: str | None = None,
        device_fingerprint: str | None = None,
        timeout: float = 10.0,
    ) -> fraud_evaluation_pb2.EvaluateResponse:  # pyright: ignore[reportAttributeAccessIssue]
        """Call the fraud evaluation gRPC service and return the response."""
        request = fraud_evaluation_pb2.EvaluateRequest(  # pyright: ignore[reportAttributeAccessIssue]
            external_id=external_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            transaction_type=transaction_type,
            channel=channel,
            merchant_name=merchant_name or "",
            merchant_category=merchant_category or "",
            location_country=location_country or "",
            ip_address=ip_address or "",
            device_fingerprint=device_fingerprint or "",
        )

        stub = self._get_stub()
        response = await stub.Evaluate(request, timeout=timeout)
        return response

    async def close(self):
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None
