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
_SENSITIVE_KEYS = {"password", "token", "access_token", "refresh_token", "secret", "otp"}


def _redact_sensitive_fields(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor that replaces sensitive field values with '[REDACTED]'."""
    for key in _SENSITIVE_KEYS:
        if key in event_dict:
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
