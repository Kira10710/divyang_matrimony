"""
Exception-to-HTTP-response mapping.

Catches domain exceptions from the service layer and returns
structured JSON error responses using the standard envelope (Section 3.8).
Unhandled exceptions return a generic 500 — never leak internals.

See Architecture Section 3.4.
"""
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppException,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PaymentError,
    RateLimitError,
    UnauthorizedError,
)
from app.core.response import error_response

logger = structlog.get_logger()

# Map exception types to HTTP status codes.
#
# Keyed by base exception class only (e.g. `UnauthorizedError`) — auth's
# more specific subclasses (`InvalidTokenError`, `TokenExpiredError`,
# `AccountLockedError`, `OtpError`, `OtpRateLimitError`, `AccountBannedError`,
# ...) all inherit their status code from here via `_resolve_status_code`'s
# MRO walk below, so a new subclass never needs a new entry.
_STATUS_MAP: dict[type[AppException], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    ForbiddenError: 403,
    BadRequestError: 400,
    PaymentError: 402,
    RateLimitError: 429,
    UnauthorizedError: 401,
}


def _resolve_status_code(exc: AppException) -> int:
    """Looks up `_STATUS_MAP` by walking `exc`'s MRO, not just its exact
    type — an exact-type `dict.get` would send every subclass (e.g.
    `InvalidTokenError`, a `UnauthorizedError` subclass) to the 500 default
    instead of the 401 its base class maps to."""
    for cls in type(exc).__mro__:
        if cls in _STATUS_MAP:
            return _STATUS_MAP[cls]
    return 500


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        status_code = _resolve_status_code(exc)
        return JSONResponse(
            status_code=status_code,
            content=error_response(
                message=exc.message,
                errors=[{"field": None, "code": exc.code, "message": exc.message}],
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "code": "VALIDATION_ERROR",
                "message": err.get("msg", "Invalid value"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response(message="Validation failed", errors=errors),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=error_response(
                message="Internal server error",
                errors=[{"field": None, "code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}],
            ),
        )
