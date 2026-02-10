"""Declarative filters for Customer queries."""

from __future__ import annotations

from typing import Optional

from fastapi_filter.contrib.sqlalchemy import Filter

from app.models.customer import Customer


class CustomerFilter(Filter):
    """FilterSet for customer list queries.

    Supported query params::

        ?status=active
        ?tier=premium
        ?order_by=created_at
    """

    status: Optional[str] = None
    tier: Optional[str] = None
    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = Customer
