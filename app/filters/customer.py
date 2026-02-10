"""Declarative filters for Customer queries."""

from __future__ import annotations

from app.filters.base import Filter
from app.models.customer import Customer


class CustomerFilter(Filter):
    """FilterSet for customer list queries.

    Supported query params::

        ?status=active
        ?tier=premium
        ?order_by=created_at
    """

    status: str | None = None
    tier: str | None = None
    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = Customer
