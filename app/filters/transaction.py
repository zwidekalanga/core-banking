"""Declarative filters for Transaction queries."""

from __future__ import annotations

from datetime import datetime

from app.filters.base import Filter
from app.models.transaction import Transaction


class TransactionFilter(Filter):
    """FilterSet for transaction list queries.

    Supported query params::

        ?customer_id=CUST-001
        ?account_id=ACC-001
        ?type=purchase
        ?channel=online
        ?created_at__gte=2024-01-01T00:00:00
        ?created_at__lte=2024-12-31T23:59:59
        ?order_by=-created_at
    """

    customer_id: str | None = None
    account_id: str | None = None
    type: str | None = None
    channel: str | None = None
    created_at__gte: datetime | None = None
    created_at__lte: datetime | None = None
    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = Transaction
