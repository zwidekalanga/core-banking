"""Declarative filters for Transaction queries."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

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

    customer_id: Optional[str] = None
    account_id: Optional[str] = None
    type: Optional[str] = None
    channel: Optional[str] = None
    created_at__gte: Optional[datetime] = None
    created_at__lte: Optional[datetime] = None
    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = Transaction
