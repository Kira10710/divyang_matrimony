"""When PostgreSQL is required (CI), prove the suite really runs on a migrated PostgreSQL database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.environ.get("REQUIRE_POSTGRES_TESTS") != "1",
    reason="only enforced when REQUIRE_POSTGRES_TESTS=1 (CI)",
)


async def test_suite_is_running_on_postgresql_at_the_migration_head(db_engine) -> None:
    assert db_engine.dialect.name == "postgresql"

    backend = Path(__file__).resolve().parents[2]
    head = ScriptDirectory.from_config(Config(str(backend / "alembic.ini"))).get_current_head()
    async with db_engine.connect() as conn:
        current = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert current == head, "database is not at the Alembic head; run scripts/migrate.py first"
