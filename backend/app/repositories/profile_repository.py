"""
ProfileRepository — abstract interface and concrete SQLAlchemy implementation.

See Architecture §3.3, Database.md §3.2.
"""
import uuid
from abc import ABC, abstractmethod

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.profile import Profile
from app.repositories.base import BaseRepository


class IProfileRepository(ABC):

    @abstractmethod
    async def get_by_id(self, profile_id: uuid.UUID) -> Profile | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None: ...

    @abstractmethod
    async def get_by_id_with_relations(self, profile_id: uuid.UUID) -> Profile | None: ...

    @abstractmethod
    async def create(self, data: dict) -> Profile: ...

    @abstractmethod
    async def update(self, profile: Profile, data: dict) -> Profile: ...

    @abstractmethod
    async def exists_for_user(self, user_id: uuid.UUID) -> bool: ...


class ProfileRepository(BaseRepository[Profile], IProfileRepository):

    def __init__(self, db: AsyncSession):
        super().__init__(Profile, db)

    async def get_by_id(self, profile_id: uuid.UUID) -> Profile | None:
        result = await self.db.execute(
            select(Profile).where(
                and_(Profile.id == profile_id, Profile.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        result = await self.db.execute(
            select(Profile).where(
                and_(Profile.user_id == user_id, Profile.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, profile_id: uuid.UUID) -> Profile | None:
        """Load profile with sensitive_data and partner_preferences eagerly."""
        result = await self.db.execute(
            select(Profile)
            .options(
                selectinload(Profile.sensitive_data),
                selectinload(Profile.partner_preferences),
            )
            .where(
                and_(Profile.id == profile_id, Profile.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Profile:
        return await super().create(data)

    async def update(self, profile: Profile, data: dict) -> Profile:
        return await super().update(profile, data)

    async def exists_for_user(self, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Profile.id).where(
                and_(Profile.user_id == user_id, Profile.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none() is not None
