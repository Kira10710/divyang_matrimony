"""
clean_db.py — developer-local schema reset tool.

DANGER: This script drops and recreates the entire public schema.
It is ONLY safe to run against a **local development test database**.

Usage (requires explicit opt-in):
    CONFIRM_CLEAN_DB=yes python clean_db.py --confirm

Guards enforced before any SQL is executed:
  1. ENVIRONMENT must equal "development".
  2. --confirm flag AND CONFIRM_CLEAN_DB=yes must both be present.
  3. DATABASE_URL must target a recognized test-named database
     (name starts with "test_", ends with "_test", or is exactly "test").
  4. DATABASE_URL host must be a local address (localhost, 127.0.0.1, ::1).

None of these guards can be bypassed by passing a different database URL at
runtime — the guard re-reads DATABASE_URL from the *current* environment after
config is loaded.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.db_guard import DatabaseSafetyError, assert_safe_clean_db_url


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drop and recreate the public PostgreSQL schema (dev/test only).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required explicit confirmation flag. Must be combined with CONFIRM_CLEAN_DB=yes.",
    )
    return parser.parse_args()


async def _drop_and_recreate(database_url: str) -> None:
    """Execute the destructive schema reset.  Only reached after guards pass."""
    engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        print("Database schema dropped and recreated successfully.")
    finally:
        await engine.dispose()


def main() -> None:
    args = _parse_args()

    # --confirm flag check
    cli_confirmed = args.confirm

    # CONFIRM_CLEAN_DB=yes env-var check
    env_confirmed = os.environ.get("CONFIRM_CLEAN_DB", "").strip().lower() == "yes"

    # Both must be set — defence in depth so the flag alone isn't sufficient
    confirmed = cli_confirmed and env_confirmed

    current_env = os.environ.get("ENVIRONMENT", "").strip()
    database_url = settings.DATABASE_URL

    try:
        assert_safe_clean_db_url(database_url, confirmed=confirmed, env=current_env)
    except DatabaseSafetyError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        print(
            "Hint: clean_db requires ALL of the following:\n"
            "  1. ENVIRONMENT=development\n"
            "  2. --confirm flag\n"
            "  3. CONFIRM_CLEAN_DB=yes\n"
            "  4. DATABASE_URL with a test-named database on localhost\n",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(_drop_and_recreate(database_url))


if __name__ == "__main__":
    main()
