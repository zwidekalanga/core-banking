"""Async Kafka producer for publishing transaction events."""

import json
import logging

from aiokafka import AIOKafkaProducer

from app.config import get_settings

logger = logging.getLogger(__name__)

TOPIC_TRANSACTIONS_RAW = "transactions.raw"

_producer: AIOKafkaProducer | None = None


async def get_kafka_producer() -> AIOKafkaProducer:
    """Get or create the singleton Kafka producer."""
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await _producer.start()
        logger.info("Kafka producer started")
    return _producer


async def publish_transaction(transaction_data: dict[str, object]) -> None:
    """Publish a transaction event to the transactions.raw topic."""
    producer = await get_kafka_producer()
    key = transaction_data.get("external_id", "")
    await producer.send_and_wait(
        topic=TOPIC_TRANSACTIONS_RAW,
        key=key,
        value=transaction_data,
    )
    logger.info(f"Published transaction {key} to {TOPIC_TRANSACTIONS_RAW}")


async def close_kafka_producer() -> None:
    """Gracefully shut down the Kafka producer."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")
