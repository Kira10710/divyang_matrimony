"""
Structured JSON logging configuration via structlog.

See Architecture Section 3.5:
- Every log: timestamp, level, request_id, user_id, module, message
- Sensitive fields (password, token, phone) redacted by processor
- LOG_LEVEL from settings (DEBUG in dev, INFO in production)
"""
import logging
import sys

import structlog

from app.core.config import settings

# Fields that should never appear in logs
_SENSITIVE_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token", "secret", "otp",
    "authorization", "phone", "email", "fcm_token", "code", "api_key",
}
# Any key containing one of these fragments is redacted too (e.g. "jwt_secret_key").
_SENSITIVE_FRAGMENTS = ("password", "secret", "token", "authorization", "api_key")


def _redact_sensitive_fields(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor that replaces sensitive field values with '[REDACTED]'."""
    for key in list(event_dict):
        lowered = str(key).lower()
        if lowered in _SENSITIVE_KEYS or any(frag in lowered for frag in _SENSITIVE_FRAGMENTS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_sensitive_fields,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to match
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
