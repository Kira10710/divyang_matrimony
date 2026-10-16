"""
db_guard.py — reusable database safety guard.

Prevents destructive operations (TRUNCATE, DROP SCHEMA, etc.) from accidentally
targeting development, staging, or production databases.

Design decisions
----------------
* URLs are parsed **structurally** via SQLAlchemy's ``make_url()`` so that
  passwords containing words like "prod" or "localhost" never cause false
  positives or negatives.
* The module **fails closed**: a missing, empty, or malformed URL raises
  ``DatabaseSafetyError`` — not a silent no-op.
* All constants (allowed hosts, forbidden env names, required name prefix) are
  defined once in this module so conftest.py, clean_db.py, and any future
  script share a single, auditable enforcement point.
"""

from __future__ import annotations

__all__ = [
    "DatabaseSafetyError",
    "assert_safe_test_db_url",
    "assert_safe_clean_db_url",
]

import os
from typing import Final

from sqlalchemy.engine import make_url

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Environments that are never allowed to run destructive DB operations.
_FORBIDDEN_ENVIRONMENTS: Final = frozenset({"production", "prod", "staging"})

#: Hosts allowed for **test** databases (local-only enforcement).
#: "postgres" is the default Docker Compose service name used in CI.
_ALLOWED_TEST_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1", "test-db", "postgres-test", "postgres"})

#: Hosts allowed for **clean_db** operations (always local).
_ALLOWED_CLEAN_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})

# A database name is accepted as a test database only when its name:
#   • starts with "test_", OR
#   • ends with "_test", OR
#   • is exactly "test"
# This avoids false positives like "contest", "attestation", or "protein".
_TEST_NAME_PREFIXES: Final = ("test_",)
_TEST_NAME_SUFFIXES: Final = ("_test",)
_TEST_NAME_EXACT: Final = "test"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class DatabaseSafetyError(RuntimeError):
    """Raised when a database URL fails a safety check.

    Inherits from ``RuntimeError`` so existing code that catches
    ``RuntimeError`` still works; callers that want to be specific can catch
    ``DatabaseSafetyError``.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_environment() -> None:
    """Raise if the current ENVIRONMENT variable is forbidden."""
    env = os.environ.get("ENVIRONMENT", "").strip().lower()
    if env in _FORBIDDEN_ENVIRONMENTS:
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: Refusing to run in ENVIRONMENT={env!r}. "
            "Destructive database operations are not permitted in this environment."
        )


def _parse_url(url_str: str, context: str) -> object:
    """Parse *url_str* with SQLAlchemy ``make_url()``.

    Raises ``DatabaseSafetyError`` on malformed input rather than letting
    SQLAlchemy's ``ArgumentError`` propagate unchecked.
    """
    if not url_str or not url_str.strip():
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: {context} URL is empty or missing. "
            "Refusing to proceed without an explicit, validated database URL."
        )
    try:
        return make_url(url_str.strip())
    except Exception as exc:  # noqa: BLE001
        raise DatabaseSafetyError(f"CRITICAL SAFETY VIOLATION: {context} URL is malformed: {exc}") from exc


def _is_test_db_name(db_name: str) -> bool:
    """Return True only for names that unambiguously belong to a test database."""
    name = db_name.lower()
    return (
        name == _TEST_NAME_EXACT
        or any(name.startswith(p) for p in _TEST_NAME_PREFIXES)
        or any(name.endswith(s) for s in _TEST_NAME_SUFFIXES)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assert_safe_test_db_url(url_str: str) -> None:
    """Validate *url_str* as a safe test-database URL.

    Checks (in order):
    1. ENVIRONMENT is not forbidden (production / staging).
    2. URL is non-empty and parseable.
    3. Database name passes the strict test-name convention.
    4. Host is in the local-only allowlist.

    Raises ``DatabaseSafetyError`` on any violation.  Does **not** connect
    to the database — purely structural validation.
    """
    _check_environment()

    parsed = _parse_url(url_str, "TEST_DATABASE")

    db_name = (parsed.database or "").strip()
    if not db_name:
        raise DatabaseSafetyError(
            "CRITICAL SAFETY VIOLATION: TEST_DATABASE URL has no database name. "
            "Refusing to truncate an unidentified database."
        )

    if not _is_test_db_name(db_name):
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: Database name '{db_name}' does not satisfy "
            "the test-database naming convention (must start with 'test_', end with "
            "'_test', or be exactly 'test'). Refusing to connect or truncate."
        )

    host = (parsed.host or "").strip().lower()
    if host not in _ALLOWED_TEST_HOSTS:
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: Host '{host}' is not in the test-database "
            f"allowlist {sorted(_ALLOWED_TEST_HOSTS)}. "
            "Test databases must run on a local or CI-internal host."
        )


def assert_safe_clean_db_url(url_str: str, *, confirmed: bool, env: str) -> None:
    """Validate *url_str* for use by ``clean_db.py``.

    Additional requirements beyond ``assert_safe_test_db_url``:

    * *confirmed* must be ``True`` — the caller must have received explicit
      operator confirmation before invoking this function.
    * *env* must equal ``"development"`` — prevents accidental use in CI or
      staging by checking the *caller-supplied* value rather than (just) the
      environment variable so scripts can enforce their own check.
    * Host must be in the stricter ``_ALLOWED_CLEAN_HOSTS`` set (no CI
      service aliases — clean_db is a developer-local tool).

    Raises ``DatabaseSafetyError`` on any violation.
    """
    if not confirmed:
        raise DatabaseSafetyError(
            "CRITICAL SAFETY VIOLATION: clean_db requires explicit confirmation "
            "(pass --confirm and set CONFIRM_CLEAN_DB=yes). Aborting."
        )

    if env.strip().lower() != "development":
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: clean_db may only run in ENVIRONMENT=development, got '{env}'. Aborting."
        )

    _check_environment()

    parsed = _parse_url(url_str, "CLEAN_DB DATABASE")

    db_name = (parsed.database or "").strip()
    if not db_name:
        raise DatabaseSafetyError("CRITICAL SAFETY VIOLATION: DATABASE_URL has no database name. Aborting.")

    if not _is_test_db_name(db_name):
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: clean_db refuses to operate on database "
            f"'{db_name}' because its name does not match the test-database convention "
            "(must start with 'test_', end with '_test', or be exactly 'test'). "
            "If you really need to drop a non-test database, do it manually."
        )

    host = (parsed.host or "").strip().lower()
    if host not in _ALLOWED_CLEAN_HOSTS:
        raise DatabaseSafetyError(
            f"CRITICAL SAFETY VIOLATION: clean_db refuses to connect to host '{host}'. "
            f"Only {sorted(_ALLOWED_CLEAN_HOSTS)} are permitted. "
            "clean_db is a local developer tool — never run it against a remote host."
        )
