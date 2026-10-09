"""
PlatformConfigRepository — reads platform_config for validation rules.

See Database.md §3.20.
"""
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_config import PlatformConfig
from app.repositories.base import BaseRepository


class IPlatformConfigRepository(ABC):

    @abstractmethod
    async def get_by_key(self, platform_key: str) -> PlatformConfig | None: ...


class PlatformConfigRepository(BaseRepository[PlatformConfig], IPlatformConfigRepository):

    def __init__(self, db: AsyncSession):
        super().__init__(PlatformConfig, db)

    async def get_by_key(self, platform_key: str) -> PlatformConfig | None:
        result = await self.db.execute(
            select(PlatformConfig).where(
                PlatformConfig.platform_key == platform_key
            )
        )
        return result.scalar_one_or_none()
