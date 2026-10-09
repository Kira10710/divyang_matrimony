"""
Common Pydantic schemas: pagination, API response envelope, error details.

These are used across all feature schemas.
See Architecture Section 3.8 for the standard response format.
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --- Pagination ---

class PaginationParams(BaseModel):
    """Cursor-based pagination parameters (not offset-based).
    Uses (created_at, id) as cursor for stable pagination across insertions.
    See Architecture Section 4.4."""
    cursor: str | None = Field(None, description="Pagination cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response with cursor for next page."""
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None  # Optional — expensive for large tables


# --- Standard Error Detail ---

class ErrorDetail(BaseModel):
    """Individual field-level error in the standard envelope."""
    field: str | None = None
    code: str
    message: str


# --- Standard API Response Envelope ---

class ApiResponse(BaseModel, Generic[T]):
    """
    Standard response envelope wrapping ALL API responses.

    Success: {"success": true, "message": "...", "data": {...}, "errors": null}
    Error:   {"success": false, "message": "...", "data": null, "errors": [...]}
    """
    success: bool
    message: str
    data: T | None = None
    errors: list[ErrorDetail] | None = None


# --- Simple ID Response ---

class IdResponse(BaseModel):
    """Response containing just an ID (e.g., after creating a resource)."""
    id: str


# --- Message Response ---

class MessageResponse(BaseModel):
    """Response containing just a message (e.g., after a delete operation)."""
    message: str
