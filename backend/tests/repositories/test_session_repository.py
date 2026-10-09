"""
Repository + session-lifecycle tests for
`app.repositories.session_repository.SessionRepository`.

Covers both halves of that module: `active_sessions` (the revocation store)
and `login_history` (the append-only audit log) — see Architecture §7.7.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.login_history import LoginEventTypeEnum
from app.repositories.session_repository import SessionRepository

PLATFORM = "divyang_matrimony"


def _future(days: int = 30) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _past(days: int = 1) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


class TestCreateSession:
    async def test_creates_and_returns_the_session(self, db_session: AsyncSession) -> None:
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())

        session = await SessionRepository(db_session).create_session(
            user_id=user_id,
            refresh_token_jti=jti,
            expires_at=_future(),
            device_info="Pixel 7",
            ip_address="127.0.0.1",
            platform_id=PLATFORM,
        )

        assert session.id is not None
        assert session.user_id == user_id
        assert session.refresh_token_jti == jti
        assert session.is_revoked is False
        assert session.revoked_at is None


class TestGetSessionByJti:
    async def test_finds_an_existing_session(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        jti = str(uuid.uuid4())
        async with db_session_factory() as session:
            await SessionRepository(session).create_session(
                user_id=uuid.uuid4(),
                refresh_token_jti=jti,
                expires_at=_future(),
                device_info=None,
                ip_address=None,
                platform_id=PLATFORM,
            )
            await session.commit()

        async with db_session_factory() as session:
            found = await SessionRepository(session).get_session_by_jti(jti)

        assert found is not None
        assert found.refresh_token_jti == jti

    async def test_returns_none_for_an_unknown_jti(self, db_session: AsyncSession) -> None:
        assert await SessionRepository(db_session).get_session_by_jti(str(uuid.uuid4())) is None


class TestRevokeSession:
    async def test_marks_revoked_with_a_timestamp(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        session = await repo.create_session(
            user_id=uuid.uuid4(),
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info=None,
            ip_address=None,
            platform_id=PLATFORM,
        )

        await repo.revoke_session(session)

        assert session.is_revoked is True
        assert session.revoked_at is not None


class TestRevokeAllSessions:
    async def test_revokes_only_that_users_active_sessions(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        async with db_session_factory() as session:
            repo = SessionRepository(session)
            await repo.create_session(
                user_id=user_id,
                refresh_token_jti=str(uuid.uuid4()),
                expires_at=_future(),
                device_info="Device A",
                ip_address=None,
                platform_id=PLATFORM,
            )
            await repo.create_session(
                user_id=user_id,
                refresh_token_jti=str(uuid.uuid4()),
                expires_at=_future(),
                device_info="Device B",
                ip_address=None,
                platform_id=PLATFORM,
            )
            await repo.create_session(
                user_id=other_user_id,
                refresh_token_jti=str(uuid.uuid4()),
                expires_at=_future(),
                device_info="Someone Else's Device",
                ip_address=None,
                platform_id=PLATFORM,
            )
            await session.commit()

        async with db_session_factory() as session:
            revoked_count = await SessionRepository(session).revoke_all_sessions(user_id)
            await session.commit()

        assert revoked_count == 2

        async with db_session_factory() as session:
            repo = SessionRepository(session)
            assert await repo.list_active_sessions(user_id) == []
            assert len(await repo.list_active_sessions(other_user_id)) == 1

    async def test_does_not_touch_already_revoked_sessions(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        user_id = uuid.uuid4()
        async with db_session_factory() as session:
            repo = SessionRepository(session)
            already_revoked = await repo.create_session(
                user_id=user_id,
                refresh_token_jti=str(uuid.uuid4()),
                expires_at=_future(),
                device_info=None,
                ip_address=None,
                platform_id=PLATFORM,
            )
            await repo.revoke_session(already_revoked)
            await session.commit()

        async with db_session_factory() as session:
            revoked_count = await SessionRepository(session).revoke_all_sessions(user_id)

        assert revoked_count == 0

    async def test_expired_sessions_are_not_counted(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        user_id = uuid.uuid4()
        async with db_session_factory() as session:
            await SessionRepository(session).create_session(
                user_id=user_id,
                refresh_token_jti=str(uuid.uuid4()),
                expires_at=_past(),
                device_info=None,
                ip_address=None,
                platform_id=PLATFORM,
            )
            await session.commit()

        async with db_session_factory() as session:
            revoked_count = await SessionRepository(session).revoke_all_sessions(user_id)

        assert revoked_count == 0


class TestListActiveSessions:
    async def test_excludes_revoked_sessions(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        user_id = uuid.uuid4()
        revoked = await repo.create_session(
            user_id=user_id,
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info=None,
            ip_address=None,
            platform_id=PLATFORM,
        )
        await repo.revoke_session(revoked)
        await repo.create_session(
            user_id=user_id,
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info=None,
            ip_address=None,
            platform_id=PLATFORM,
        )

        active = await repo.list_active_sessions(user_id)

        assert len(active) == 1
        assert active[0].is_revoked is False

    async def test_excludes_expired_sessions(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        user_id = uuid.uuid4()
        await repo.create_session(
            user_id=user_id,
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_past(),
            device_info=None,
            ip_address=None,
            platform_id=PLATFORM,
        )

        assert await repo.list_active_sessions(user_id) == []

    async def test_orders_newest_first(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        user_id = uuid.uuid4()
        older = await repo.create_session(
            user_id=user_id,
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info="Older",
            ip_address=None,
            platform_id=PLATFORM,
        )
        older.created_at = datetime.now(UTC) - timedelta(hours=1)
        newer = await repo.create_session(
            user_id=user_id,
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info="Newer",
            ip_address=None,
            platform_id=PLATFORM,
        )
        await db_session.flush()

        active = await repo.list_active_sessions(user_id)

        assert [s.id for s in active] == [newer.id, older.id]


class TestTouchSession:
    async def test_updates_last_used_at(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        session = await repo.create_session(
            user_id=uuid.uuid4(),
            refresh_token_jti=str(uuid.uuid4()),
            expires_at=_future(),
            device_info=None,
            ip_address=None,
            platform_id=PLATFORM,
        )
        assert session.last_used_at is None

        await repo.touch_session(session)

        assert session.last_used_at is not None


class TestLogEvent:
    async def test_appends_a_login_history_row(self, db_session: AsyncSession) -> None:
        repo = SessionRepository(db_session)
        user_id = uuid.uuid4()

        entry = await repo.log_event(
            user_id=user_id,
            event_type=LoginEventTypeEnum.LOGIN_SUCCESS,
            ip_address="127.0.0.1",
            user_agent="pytest",
            device_info="Pixel 7",
            refresh_token_jti="some-jti",
            is_suspicious=False,
            platform_id=PLATFORM,
        )

        assert entry.id is not None
        assert entry.user_id == user_id
        assert entry.event_type == LoginEventTypeEnum.LOGIN_SUCCESS
        assert entry.is_suspicious is False

    async def test_records_a_suspicious_login(self, db_session: AsyncSession) -> None:
        entry = await SessionRepository(db_session).log_event(
            user_id=uuid.uuid4(),
            event_type=LoginEventTypeEnum.LOGIN_SUCCESS,
            ip_address=None,
            user_agent=None,
            device_info="New Device",
            refresh_token_jti=None,
            is_suspicious=True,
            platform_id=PLATFORM,
        )

        assert entry.is_suspicious is True


class TestSessionLifecycle:
    """A full create → list → revoke → list journey, in one place."""

    async def test_full_lifecycle(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())

        async with db_session_factory() as session:
            await SessionRepository(session).create_session(
                user_id=user_id,
                refresh_token_jti=jti,
                expires_at=_future(),
                device_info="Pixel 7",
                ip_address="127.0.0.1",
                platform_id=PLATFORM,
            )
            await session.commit()

        async with db_session_factory() as session:
            active = await SessionRepository(session).list_active_sessions(user_id)
        assert len(active) == 1

        async with db_session_factory() as session:
            repo = SessionRepository(session)
            found = await repo.get_session_by_jti(jti)
            assert found is not None
            await repo.revoke_session(found)
            await session.commit()

        async with db_session_factory() as session:
            assert await SessionRepository(session).list_active_sessions(user_id) == []
