"""Common schemas shared across the API."""

from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    """Base paginated response."""

    total: int
    page: int
    size: int
    pages: int
