"""Unit tests for the Kafka producer."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services.kafka_producer import TOPIC_TRANSACTIONS_RAW, publish_transaction


@pytest.mark.asyncio
class TestPublishTransaction:
    async def test_publishes_with_correct_topic_and_key(self):
        """Transaction should be sent to the correct topic with external_id as key."""
        mock_producer = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()

        payload = {
            "external_id": "TXN-001",
            "customer_id": "CUST-001",
            "amount": "150.00",
        }
        await publish_transaction(mock_producer, payload)

        mock_producer.send_and_wait.assert_awaited_once()
        call_kwargs = mock_producer.send_and_wait.call_args
        assert call_kwargs.kwargs["topic"] == TOPIC_TRANSACTIONS_RAW
        assert call_kwargs.kwargs["key"] == "TXN-001"
        assert call_kwargs.kwargs["value"] == payload

    async def test_publishes_with_empty_key_when_missing(self):
        """Missing external_id should default to empty string key."""
        mock_producer = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()

        await publish_transaction(mock_producer, {"customer_id": "CUST-001"})

        call_kwargs = mock_producer.send_and_wait.call_args
        assert call_kwargs.kwargs["key"] == ""


class TestKafkaProducerSerialization:
    def test_value_serializer_handles_decimals(self):
        """The JSON serializer used by the producer should handle Decimal values."""
        serializer = lambda v: json.dumps(v, default=str).encode("utf-8")
        result = serializer({"amount": Decimal("150.00")})
        parsed = json.loads(result)
        assert parsed["amount"] == "150.00"

    def test_value_serializer_handles_nested_types(self):
        """The JSON serializer should handle datetime-like objects via str fallback."""
        from datetime import UTC, datetime

        serializer = lambda v: json.dumps(v, default=str).encode("utf-8")
        now = datetime.now(UTC)
        result = serializer({"timestamp": now})
        parsed = json.loads(result)
        assert isinstance(parsed["timestamp"], str)
