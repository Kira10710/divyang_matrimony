"""
PartnerPreferenceRepository — manages partner_preferences table.

See Database.md §3.5.
"""
import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner_preference import PartnerPreference
from app.repositories.base import BaseRepository


class IPartnerPreferenceRepository(ABC):

    @abstractmethod
    async def get_by_profile_id(self, profile_id: uuid.UUID) -> PartnerPreference | None: ...

    @abstractmethod
    async def create(self, data: dict) -> PartnerPreference: ...

    @abstractmethod
    async def update(self, record: PartnerPreference, data: dict) -> PartnerPreference: ...


class PartnerPreferenceRepository(BaseRepository[PartnerPreference], IPartnerPreferenceRepository):

    def __init__(self, db: AsyncSession):
        super().__init__(PartnerPreference, db)

    async def get_by_profile_id(self, profile_id: uuid.UUID) -> PartnerPreference | None:
        result = await self.db.execute(
            select(PartnerPreference).where(
                PartnerPreference.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> PartnerPreference:
        return await super().create(data)

    async def update(self, record: PartnerPreference, data: dict) -> PartnerPreference:
        return await super().update(record, data)
