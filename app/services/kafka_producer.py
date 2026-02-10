"""Async Kafka producer for publishing transaction events."""

import json

from aiokafka import AIOKafkaProducer

from app.config import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

TOPIC_TRANSACTIONS_RAW = "transactions.raw"


async def create_kafka_producer(settings: Settings) -> AIOKafkaProducer:
    """Create and start a Kafka producer. Caller owns the lifecycle."""
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )
    await producer.start()
    logger.info("Kafka producer started")
    return producer


async def publish_transaction(
    producer: AIOKafkaProducer, transaction_data: dict[str, object]
) -> None:
    """Publish a transaction event to the transactions.raw topic."""
    key = transaction_data.get("external_id", "")
    await producer.send_and_wait(
        topic=TOPIC_TRANSACTIONS_RAW,
        key=key,
        value=transaction_data,
    )
    logger.info("Published transaction %s to %s", key, TOPIC_TRANSACTIONS_RAW)
