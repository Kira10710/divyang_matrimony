"""
UserRepository — abstract interface and concrete SQLAlchemy implementation.

Pattern: interface defined first, implementation depends only on the interface.
The service layer depends on the interface, never the implementation directly.
See Architecture §3.3 (Clean Architecture, Repository Pattern).
"""
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository

# ---------------------------------------------------------------------------
# Interface (Port)
# ---------------------------------------------------------------------------

class IUserRepository(ABC):
    """Abstract interface for user persistence operations."""

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a non-deleted user by primary key."""
        ...

    @abstractmethod
    async def get_by_phone(self, phone: str, platform_id: str) -> User | None:
        """Get a non-deleted user by phone + platform."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str, platform_id: str) -> User | None:
        """Get a non-deleted user (admin) by email + platform."""
        ...

    @abstractmethod
    async def create(self, data: dict) -> User:
        """Create and flush a new user row."""
        ...

    @abstractmethod
    async def update_last_login(self, user: User, fcm_token: str | None = None) -> User:
        """Update last_login_at and optionally FCM token."""
        ...

    @abstractmethod
    async def update_phone_verified(self, user: User) -> User:
        """Mark phone as verified."""
        ...

    @abstractmethod
    async def soft_delete(self, user: User) -> User:
        """Soft-delete user by setting deleted_at."""
        ...


# ---------------------------------------------------------------------------
# Implementation (Adapter)
# ---------------------------------------------------------------------------

class UserRepository(BaseRepository[User], IUserRepository):
    """Concrete async SQLAlchemy user repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
        Get a non-soft-deleted user by primary key.

        Filters out deleted_at IS NOT NULL so callers never accidentally
        operate on a user in the 30-day cooling-off window.
        """
        result = await self.db.execute(
            select(User).where(
                and_(User.id == user_id, User.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str, platform_id: str) -> User | None:
        """Get active user by E.164 phone + platform_id."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.phone == phone,
                    User.platform_id == platform_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str, platform_id: str) -> User | None:
        """Get active user (admin) by email + platform_id."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.platform_id == platform_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> User:
        """Create and flush (not commit) a new user."""
        return await super().create(data)

    async def update_last_login(
        self, user: User, fcm_token: str | None = None
    ) -> User:
        """Update last_login_at timestamp and optionally the FCM token."""
        updates: dict = {"last_login_at": datetime.now(UTC)}
        if fcm_token is not None:
            updates["fcm_token"] = fcm_token
        return await super().update(user, updates)

    async def update_phone_verified(self, user: User) -> User:
        """Mark user.is_phone_verified = True."""
        return await super().update(user, {"is_phone_verified": True})

    async def soft_delete(self, user: User) -> User:
        """
        Soft-delete user — sets deleted_at to now.

        The scheduled_jobs.py purge job handles actual PII deletion after
        the 30-day cooling-off window (Database.md §5 hard-purge sequence).
        """
        return await super().soft_delete(user)
