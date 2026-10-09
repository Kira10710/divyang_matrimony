"""
Shared pytest fixtures for the backend test suite.

Env vars are set *before* anything is imported from `app` — `app.core.config
.Settings()` is instantiated at import time and has no defaults for secrets
(Architecture §3.2: "the app fails to start if a required secret is
missing"), so importing `app.core.config` (transitively, via almost
anything) without these set first raises a `ValidationError` immediately.

Database strategy (Architecture §3.1 says PostgreSQL-only — there is no
"test mode" driver switch in the app itself):
    `DATABASE_URL` below stays a syntactically-valid `postgresql+asyncpg`
    URL purely so `app.core.database`'s module-level `create_async_engine()`
    call succeeds at import time. It is never connected to — every test
    that touches a database uses the isolated in-memory SQLite engine from
    `db_engine`/`db_session` instead, wired in via FastAPI dependency
    overrides (`app_client`) or used directly (repository tests). See the
    SQLite compatibility shims below for why plain SQLite needed help.
"""
from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("PLATFORM_ID", "divyang_matrimony")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db_unused")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
# >=32 bytes to avoid PyJWT's InsecureKeyLengthWarning cluttering test output.
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-secret-key-do-not-use-in-production-32bytes+")
os.environ.setdefault("FIREBASE_CREDENTIALS_PATH", "test-fixtures/dummy-firebase-credentials.json")
os.environ.setdefault("FIREBASE_STORAGE_BUCKET", "test-bucket.appspot.com")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_dummy")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "dummy_key_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "dummy_webhook_secret")
# 64 hex chars = 32 bytes for AES-256 (test-only key, never use in production)
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "0" * 64)

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import sqlalchemy.types as sqltypes
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, TSVECTOR
from sqlalchemy.dialects.sqlite.aiosqlite import SQLiteDialect_aiosqlite
from sqlalchemy.dialects.sqlite.base import DATETIME as SQLiteDateTime  # noqa: N811
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# SQLite compatibility shims (test-only — production always runs on
# PostgreSQL per Architecture §3.1). Registered once, at collection time,
# before any engine is created.
# ---------------------------------------------------------------------------

# 1) SQLite has no INET type; the DDL compiler otherwise raises
#    `CompileError` on `active_sessions.ip_address` / `login_history.ip_address`.
@compiles(INET, "sqlite")
def _compile_inet_as_varchar(element: object, compiler: object, **kw: object) -> str:
    return "VARCHAR(45)"


# 3) SQLite has no JSONB type (used by platform_config.settings).
@compiles(JSONB, "sqlite")
def _compile_jsonb_as_text(element: object, compiler: object, **kw: object) -> str:
    return "TEXT"


# 4) SQLite has no TSVECTOR type (used by profiles.search_vector).
@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_as_text(element: object, compiler: object, **kw: object) -> str:
    return "TEXT"


# 5) SQLite has no native ARRAY type (used by partner_preferences).
#    Map to TEXT — the values are not read back by SQLite tests.
@compiles(ARRAY, "sqlite")
def _compile_array_as_text(element: object, compiler: object, **kw: object) -> str:
    return "TEXT"



# 2) SQLAlchemy's generic sqlite DATETIME type parses stored ISO strings back
#    into *naive* datetimes — SQLite has no real tz-aware storage, unlike
#    PostgreSQL's TIMESTAMPTZ (which asyncpg round-trips as aware). Without
#    this, any comparison against an aware `datetime.now(timezone.utc)"
#    (e.g. `AuthService.refresh_tokens`'s expiry check) raises
#    `TypeError: can't compare offset-naive and offset-aware datetimes` —
#    not an application bug, a SQLite-testing-only gap. Re-attach UTC.
class _UTCSQLiteDateTime(SQLiteDateTime):
    def result_processor(self, dialect: object, coltype: object) -> Callable[[object], object]:
        processor = super().result_processor(dialect, coltype)

        def process(value: object) -> object:
            dt = processor(value) if processor else value
            if isinstance(dt, datetime) and dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt

        return process

import json

from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.types import String, TypeDecorator


class _SQLiteArray(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps([v.value if hasattr(v, 'value') else v for v in value])
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

SQLiteDialect_aiosqlite.colspecs = {
    **SQLiteDialect_aiosqlite.colspecs,
    sqltypes.DateTime: _UTCSQLiteDateTime,
    PG_ARRAY: _SQLiteArray,
}

# ---------------------------------------------------------------------------
# App imports — safe now that env vars + SQLite shims are in place.
# ---------------------------------------------------------------------------
from app.core.database import get_db  # noqa: E402
from app.core.dependencies import get_otp_service  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import AdminRoleEnum, Base, User  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402
from app.services.otp_service import RedisOtpService  # noqa: E402

from .factories.user_factory import AdminUserFactory, UserFactory  # noqa: E402
from .fakes import FakeRedis  # noqa: E402

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """A fresh, isolated in-memory SQLite database per test, schema created
    from the real ORM models (`app.models`)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session factory bound to the per-test engine.

    Prefer this over `db_session` whenever a test needs to mimic
    production's one-session-per-request lifecycle — e.g. creating a row in
    one session and then observing it via a fresh one. Reusing a single
    session across an ORM `update()` and a later read can otherwise trip
    SQLAlchemy's client-side "evaluate" synchronization strategy on stale
    in-memory objects, which is a SQLite-session-identity-map quirk, not
    something worth working around in application code.
    """
    return async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A single `AsyncSession` — the common case for tests that only need one."""
    async with db_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Test data fixtures (factory_boy builds the input dict; persistence goes
# through the app's own repositories, so tests exercise the real create path)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_user(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[User]]:
    """Factory fixture: `await make_user(phone="+919876543210")` persists and
    returns a regular end-user `User` row. Unset fields are Faker-generated."""

    async def _make(**overrides: object) -> User:
        async with db_session_factory() as session:
            user = await UserRepository(session).create(UserFactory(**overrides))
            await session.commit()
            return user

    return _make


@pytest_asyncio.fixture
async def make_admin(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[User]]:
    """Factory fixture for an admin account. Pass `password="..."` to control
    the plaintext password used to derive `password_hash` (defaults to
    `"CorrectHorseBattery1"`) — tests need the plaintext to exercise login."""

    async def _make(*, password: str = "CorrectHorseBattery1", **overrides: object) -> User:  # noqa: S107
        overrides.setdefault("role", AdminRoleEnum.ADMIN)
        overrides["password_hash"] = hash_password(password)
        async with db_session_factory() as session:
            admin = await UserRepository(session).create(AdminUserFactory(**overrides))
            await session.commit()
            return admin

    return _make


# ---------------------------------------------------------------------------
# API client fixture — full FastAPI app, real routing/middleware/exception
# handlers, `get_db` overridden to the SQLite test database, `get_otp_service`
# overridden to a real `RedisOtpService` backed by `FakeRedis` (exercises the
# actual OTP/rate-limit/lockout logic, not a hand-rolled re-implementation
# of it — only the Redis I/O boundary is faked).
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def app_client(
    db_session_factory: async_sessionmaker[AsyncSession],
    fake_redis: FakeRedis,
) -> Iterator[TestClient]:
    from app.main import app

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    otp_service = RedisOtpService(fake_redis)

    def _override_get_otp_service() -> RedisOtpService:
        return otp_service

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_otp_service] = _override_get_otp_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


@pytest.fixture
def new_jti() -> str:
    """A fresh JWT ID string, for tests that need to hand-construct an
    `active_sessions` row without going through the full login flow."""
    return str(uuid.uuid4())
