"""
SensitiveDataRepository — manages sensitive_profile_data and access logging.

See Architecture §5.2, Database.md §3.3, §3.15.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensitive_data_access_log import SensitiveDataAccessLog
from app.models.sensitive_profile_data import SensitiveProfileData
from app.repositories.base import BaseRepository


class ISensitiveDataRepository(ABC):

    @abstractmethod
    async def get_by_profile_id(self, profile_id: uuid.UUID) -> SensitiveProfileData | None: ...

    @abstractmethod
    async def create(self, data: dict) -> SensitiveProfileData: ...

    @abstractmethod
    async def update(self, record: SensitiveProfileData, data: dict) -> SensitiveProfileData: ...

    @abstractmethod
    async def log_access(
        self,
        *,
        accessor_user_id: uuid.UUID,
        target_profile_id: uuid.UUID,
        fields_accessed: list[str],
        access_tier: str,
        ip_address: str | None,
        platform_id: str,
    ) -> None: ...


class SensitiveDataRepository(BaseRepository[SensitiveProfileData], ISensitiveDataRepository):

    def __init__(self, db: AsyncSession):
        super().__init__(SensitiveProfileData, db)

    async def get_by_profile_id(self, profile_id: uuid.UUID) -> SensitiveProfileData | None:
        result = await self.db.execute(
            select(SensitiveProfileData).where(
                and_(
                    SensitiveProfileData.profile_id == profile_id,
                    SensitiveProfileData.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> SensitiveProfileData:
        return await super().create(data)

    async def update(self, record: SensitiveProfileData, data: dict) -> SensitiveProfileData:
        return await super().update(record, data)

    async def log_access(
        self,
        *,
        accessor_user_id: uuid.UUID,
        target_profile_id: uuid.UUID,
        fields_accessed: list[str],
        access_tier: str,
        ip_address: str | None,
        platform_id: str,
    ) -> None:
        """
        Append an immutable access log entry.

        Volume control (§5.2): only called for SUBSCRIBERS/MATCHED/PRIVATE reads,
        never for PUBLIC-tier disability_type shown in search results.
        """
        entry = SensitiveDataAccessLog(
            accessor_user_id=accessor_user_id,
            target_profile_id=target_profile_id,
            fields_accessed=fields_accessed,
            access_tier=access_tier,
            ip_address=ip_address,
            platform_id=platform_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(entry)
        await self.db.flush()
