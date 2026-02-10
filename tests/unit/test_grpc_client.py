"""Unit tests for the gRPC fraud evaluation client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.grpc.fraud_client import FraudEvaluationClient


@pytest.mark.asyncio
class TestFraudEvaluationClient:
    async def test_evaluate_calls_stub(self):
        """Client should build a request and call the gRPC stub."""
        mock_response = SimpleNamespace(
            risk_score=25,
            decision="APPROVE",
            decision_tier="low",
            decision_tier_description="Low risk",
            triggered_rules=[],
            processing_time_ms=5.0,
            alert_created=False,
            alert_id="",
        )

        client = FraudEvaluationClient(target="localhost:50051")

        mock_stub = MagicMock()
        mock_stub.Evaluate = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_stub", return_value=mock_stub):
            result = await client.evaluate(
                external_id="TXN-001",
                customer_id="CUST-001",
                amount=100.0,
                transaction_type="purchase",
                channel="online",
            )

        assert result.risk_score == 25
        assert result.decision == "APPROVE"
        mock_stub.Evaluate.assert_awaited_once()

    async def test_evaluate_with_optional_fields(self):
        """Optional fields should default to empty strings in the gRPC request."""
        mock_response = SimpleNamespace(
            risk_score=75,
            decision="FLAG",
            decision_tier="high",
            decision_tier_description="High risk",
            triggered_rules=[
                SimpleNamespace(
                    code="AMT_001",
                    name="High Amount",
                    category="amount",
                    severity="high",
                    score=75,
                    description="Amount exceeds threshold",
                )
            ],
            processing_time_ms=8.0,
            alert_created=True,
            alert_id="ALERT-001",
        )

        client = FraudEvaluationClient(target="localhost:50051")
        mock_stub = MagicMock()
        mock_stub.Evaluate = AsyncMock(return_value=mock_response)

        with patch.object(client, "_get_stub", return_value=mock_stub):
            result = await client.evaluate(
                external_id="TXN-002",
                customer_id="CUST-002",
                amount=999999.99,
                transaction_type="purchase",
                channel="online",
                merchant_name="Casino",
                merchant_category="gambling",
                location_country="KP",
                ip_address="1.2.3.4",
                device_fingerprint="fp-xyz",
            )

        assert result.risk_score == 75
        assert result.alert_created is True
        assert len(result.triggered_rules) == 1

    async def test_close_channel(self):
        """close() should close the gRPC channel."""
        client = FraudEvaluationClient(target="localhost:50051")
        mock_channel = AsyncMock()
        client._channel = mock_channel
        client._stub = MagicMock()

        await client.close()

        mock_channel.close.assert_awaited_once()
        assert client._channel is None
        assert client._stub is None

    async def test_close_noop_without_channel(self):
        """close() with no channel should be a no-op."""
        client = FraudEvaluationClient(target="localhost:50051")
        await client.close()  # should not raise

    def test_target_is_stored(self):
        """Client should store the target it was initialized with."""
        client = FraudEvaluationClient(target="custom:9999")
        assert client._target == "custom:9999"
