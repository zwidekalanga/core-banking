"""Common schemas shared across the API."""

from math import ceil

from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    """Base paginated response."""

    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def paginate(cls, *, items: list, total: int, page: int, size: int, **kwargs):
        """Build a paginated response with automatic page count."""
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=ceil(total / size) if size > 0 else 0,
            **kwargs,
        )
