"""
Standard API response envelope.

Every API response uses this structure for consistency.
See Architecture Section 3.8.

Success:
    {"success": true, "message": "...", "data": {...}, "errors": null}

Error:
    {"success": false, "message": "...", "data": null, "errors": [{...}]}
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Individual field-level error."""

    field: str | None = None
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    """Standard response envelope wrapping all API responses."""

    success: bool
    message: str
    data: T | None = None
    errors: list[ErrorDetail] | None = None


def success_response(
    data: Any = None,
    message: str = "Success",
) -> dict[str, Any]:
    """Helper to construct a success response dict."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "errors": None,
    }


def error_response(
    message: str = "Error",
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Helper to construct an error response dict."""
    return {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors,
    }
