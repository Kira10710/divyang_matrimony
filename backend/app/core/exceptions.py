"""
Domain exception classes.

Service layer raises these; error_handlers.py maps them to HTTP responses.
See Architecture Section 3.4.

Exception hierarchy:
    AppException
    ├── NotFoundError          → 404
    ├── ConflictError          → 409
    ├── ForbiddenError         → 403
    ├── BadRequestError        → 400
    ├── PaymentError           → 402
    ├── RateLimitError         → 429
    └── UnauthorizedError      → 401
        ├── InvalidTokenError  → 401 (JWT decode failure)
        ├── TokenExpiredError  → 401 (JWT expired)
        └── AccountLockedError → 401 (too many failed attempts)
"""


class AppException(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, message: str = "An error occurred", code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found (maps to HTTP 404)."""

    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message, code)


class ConflictError(AppException):
    """Duplicate resource (maps to HTTP 409)."""

    def __init__(self, message: str = "Resource already exists", code: str = "CONFLICT"):
        super().__init__(message, code)


class ForbiddenError(AppException):
    """Insufficient permissions (maps to HTTP 403)."""

    def __init__(self, message: str = "Forbidden", code: str = "FORBIDDEN"):
        super().__init__(message, code)


class BadRequestError(AppException):
    """Business rule violation (maps to HTTP 400)."""

    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST"):
        super().__init__(message, code)


class PaymentError(AppException):
    """Payment processing failure (maps to HTTP 402)."""

    def __init__(self, message: str = "Payment error", code: str = "PAYMENT_ERROR"):
        super().__init__(message, code)


class RateLimitError(AppException):
    """Rate limit exceeded (maps to HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded", code: str = "RATE_LIMIT"):
        super().__init__(message, code)


class UnauthorizedError(AppException):
    """Authentication failure (maps to HTTP 401)."""

    def __init__(self, message: str = "Unauthorized", code: str = "UNAUTHORIZED"):
        super().__init__(message, code)


# --- Auth-specific subclasses ---

class InvalidTokenError(UnauthorizedError):
    """JWT token is invalid (bad signature, wrong type, malformed)."""

    def __init__(self, message: str = "Invalid or malformed token", code: str = "INVALID_TOKEN"):
        super().__init__(message, code)


class TokenExpiredError(UnauthorizedError):
    """JWT token has expired."""

    def __init__(self, message: str = "Token has expired", code: str = "TOKEN_EXPIRED"):
        super().__init__(message, code)


class AccountLockedError(UnauthorizedError):
    """Account temporarily locked due to too many failed login attempts (Architecture §7.7)."""

    def __init__(
        self,
        message: str = "Account temporarily locked due to too many failed login attempts",
        code: str = "ACCOUNT_LOCKED",
    ):
        super().__init__(message, code)


class OtpError(BadRequestError):
    """OTP verification failed — wrong code, expired, or too many attempts."""

    def __init__(self, message: str = "Invalid or expired OTP", code: str = "OTP_INVALID"):
        super().__init__(message, code)


class OtpRateLimitError(RateLimitError):
    """Too many OTP send requests for this phone number."""

    def __init__(
        self,
        message: str = "Too many OTP requests. Please wait before requesting another.",
        code: str = "OTP_RATE_LIMIT",
    ):
        super().__init__(message, code)


class AccountBannedError(ForbiddenError):
    """User account has been banned by an admin."""

    def __init__(self, message: str = "This account has been suspended", code: str = "ACCOUNT_BANNED"):
        super().__init__(message, code)
