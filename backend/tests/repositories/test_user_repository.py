"""
Repository tests for `app.repositories.user_repository.UserRepository`.

Runs against a real (in-memory SQLite) database — see `tests/conftest.py`
for the schema/dialect setup — because the whole point of this layer is its
query behavior, which a mocked `AsyncSession` can't meaningfully verify.

Where a test needs to see data *committed* by an earlier step, it opens a
fresh session via `db_session_factory` rather than reusing one — the same
one-session-per-request lifecycle production code gets from `get_db`.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import AdminRoleEnum
from app.repositories.user_repository import UserRepository

from ..factories.user_factory import AdminUserFactory, UserFactory

PLATFORM = "divyang_matrimony"


class TestCreate:
    async def test_creates_and_returns_the_user(self, db_session: AsyncSession) -> None:
        user = await UserRepository(db_session).create(UserFactory(phone="+919876543210"))

        assert user.id is not None
        assert user.phone == "+919876543210"
        assert user.platform_id == PLATFORM
        assert user.is_active is True
        assert user.is_banned is False

    async def test_creates_an_admin_with_a_role(self, db_session: AsyncSession) -> None:
        user = await UserRepository(db_session).create(
            AdminUserFactory(email="admin@example.com", role=AdminRoleEnum.ADMIN, password_hash="hash")
        )

        assert user.is_admin is True
        assert user.role == AdminRoleEnum.ADMIN
        assert user.phone is None


class TestGetById:
    async def test_finds_an_existing_user(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            created = await UserRepository(session).create(UserFactory())
            await session.commit()
            user_id = created.id

        async with db_session_factory() as session:
            found = await UserRepository(session).get_by_id(user_id)

        assert found is not None
        assert found.id == user_id

    async def test_returns_none_for_an_unknown_id(self, db_session: AsyncSession) -> None:
        assert await UserRepository(db_session).get_by_id(uuid.uuid4()) is None

    async def test_excludes_soft_deleted_users(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            repo = UserRepository(session)
            created = await repo.create(UserFactory())
            await repo.soft_delete(created)
            await session.commit()
            user_id = created.id

        async with db_session_factory() as session:
            assert await UserRepository(session).get_by_id(user_id) is None


class TestGetByPhone:
    async def test_finds_by_phone_and_platform(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            await UserRepository(session).create(UserFactory(phone="+919876543210"))
            await session.commit()

        async with db_session_factory() as session:
            found = await UserRepository(session).get_by_phone("+919876543210", PLATFORM)

        assert found is not None
        assert found.phone == "+919876543210"

    async def test_same_phone_on_a_different_platform_is_not_found(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            await UserRepository(session).create(UserFactory(phone="+919876543210"))
            await session.commit()

        async with db_session_factory() as session:
            found = await UserRepository(session).get_by_phone("+919876543210", "some_other_platform")

        assert found is None

    async def test_unknown_phone_returns_none(self, db_session: AsyncSession) -> None:
        assert await UserRepository(db_session).get_by_phone("+911111111111", PLATFORM) is None


class TestGetByEmail:
    async def test_finds_an_admin_by_email(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            await UserRepository(session).create(
                AdminUserFactory(email="admin@example.com", role=AdminRoleEnum.ADMIN, password_hash="hash")
            )
            await session.commit()

        async with db_session_factory() as session:
            found = await UserRepository(session).get_by_email("admin@example.com", PLATFORM)

        assert found is not None
        assert found.email == "admin@example.com"

    async def test_unknown_email_returns_none(self, db_session: AsyncSession) -> None:
        assert await UserRepository(db_session).get_by_email("nope@example.com", PLATFORM) is None


class TestUpdateLastLogin:
    async def test_sets_last_login_at(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = await repo.create(UserFactory())
        assert user.last_login_at is None

        updated = await repo.update_last_login(user)

        assert updated.last_login_at is not None

    async def test_optionally_updates_the_fcm_token(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = await repo.create(UserFactory())

        updated = await repo.update_last_login(user, fcm_token="fcm-token-123")

        assert updated.fcm_token == "fcm-token-123"

    async def test_omitting_fcm_token_leaves_the_existing_one_untouched(
        self, db_session: AsyncSession
    ) -> None:
        repo = UserRepository(db_session)
        user = await repo.create(UserFactory())
        await repo.update_last_login(user, fcm_token="original-token")

        updated = await repo.update_last_login(user)

        assert updated.fcm_token == "original-token"


class TestUpdatePhoneVerified:
    async def test_sets_the_flag(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = await repo.create(UserFactory(is_phone_verified=False))

        updated = await repo.update_phone_verified(user)

        assert updated.is_phone_verified is True


class TestSoftDelete:
    async def test_sets_deleted_at(self, db_session: AsyncSession) -> None:
        repo = UserRepository(db_session)
        user = await repo.create(UserFactory())

        deleted = await repo.soft_delete(user)

        assert deleted.deleted_at is not None
        assert deleted.is_deleted is True

    async def test_soft_deleted_user_cannot_be_found_by_phone(
        self, db_session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        async with db_session_factory() as session:
            repo = UserRepository(session)
            user = await repo.create(UserFactory(phone="+919876543210"))
            await repo.soft_delete(user)
            await session.commit()

        async with db_session_factory() as session:
            assert await UserRepository(session).get_by_phone("+919876543210", PLATFORM) is None
