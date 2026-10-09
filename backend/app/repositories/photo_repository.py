"""
PhotoRepository — database access for profile_photos.

All DB access goes through here; no business logic.
Services orchestrate; repositories only read/write rows.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ModerationStatusEnum
from app.models.profile_photo import ProfilePhoto

logger = structlog.get_logger(__name__)

MAX_PHOTOS_PER_PROFILE = 6  # Database.md §3.4: enforced in app layer


class IPhotoRepository(ABC):
    """Abstract interface — enables mocking in tests."""

    @abstractmethod
    async def get_by_id(self, photo_id: uuid.UUID) -> ProfilePhoto | None: ...

    @abstractmethod
    async def list_for_profile(
        self,
        profile_id: uuid.UUID,
        *,
        include_pending: bool = False,
    ) -> list[ProfilePhoto]: ...

    @abstractmethod
    async def count_for_profile(self, profile_id: uuid.UUID) -> int: ...

    @abstractmethod
    async def get_pending_photos(self, limit: int = 50, offset: int = 0) -> list[ProfilePhoto]: ...

    @abstractmethod
    async def get_primary(self, profile_id: uuid.UUID) -> ProfilePhoto | None: ...

    @abstractmethod
    async def create(self, photo: ProfilePhoto) -> ProfilePhoto: ...

    @abstractmethod
    async def update_moderation(
        self,
        photo_id: uuid.UUID,
        status: ModerationStatusEnum,
        rejection_reason: str | None = None,
    ) -> ProfilePhoto | None: ...

    @abstractmethod
    async def set_primary(
        self, profile_id: uuid.UUID, photo_id: uuid.UUID
    ) -> None: ...

    @abstractmethod
    async def delete(self, photo_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def hard_delete_all_for_profile(self, profile_id: uuid.UUID) -> int: ...


class PhotoRepository(IPhotoRepository):
    """SQLAlchemy async implementation of IPhotoRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, photo_id: uuid.UUID) -> ProfilePhoto | None:
        result = await self._db.execute(
            select(ProfilePhoto).where(ProfilePhoto.id == photo_id)
        )
        return result.scalar_one_or_none()

    async def list_for_profile(
        self,
        profile_id: uuid.UUID,
        *,
        include_pending: bool = False,
    ) -> list[ProfilePhoto]:
        """
        Return photos for a profile ordered by display_order.

        By default only APPROVED photos are returned (what viewers see).
        Pass include_pending=True to include PENDING photos (profile owner view).
        REJECTED photos are never returned by this method.
        """
        stmt = (
            select(ProfilePhoto)
            .where(ProfilePhoto.profile_id == profile_id)
            .where(ProfilePhoto.moderation_status != ModerationStatusEnum.REJECTED)
            .order_by(ProfilePhoto.display_order.asc(), ProfilePhoto.created_at.asc())
        )
        if not include_pending:
            stmt = stmt.where(
                ProfilePhoto.moderation_status == ModerationStatusEnum.APPROVED
            )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_for_profile(self, profile_id: uuid.UUID) -> int:
        """Count all non-REJECTED photos (counts against the 6-photo limit)."""
        from sqlalchemy import func
        result = await self._db.execute(
            select(func.count())
            .select_from(ProfilePhoto)
            .where(ProfilePhoto.profile_id == profile_id)
            .where(ProfilePhoto.moderation_status != ModerationStatusEnum.REJECTED)
        )
        return result.scalar_one()

    async def get_pending_photos(self, limit: int = 50, offset: int = 0) -> list[ProfilePhoto]:
        """Get photos awaiting moderation."""
        stmt = (
            select(ProfilePhoto)
            .where(ProfilePhoto.moderation_status == ModerationStatusEnum.PENDING)
            .order_by(ProfilePhoto.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_primary(self, profile_id: uuid.UUID) -> ProfilePhoto | None:
        """Return the single APPROVED primary photo, or None."""
        result = await self._db.execute(
            select(ProfilePhoto)
            .where(ProfilePhoto.profile_id == profile_id)
            .where(ProfilePhoto.is_primary.is_(True))
            .where(ProfilePhoto.moderation_status == ModerationStatusEnum.APPROVED)
        )
        return result.scalar_one_or_none()

    async def create(self, photo: ProfilePhoto) -> ProfilePhoto:
        self._db.add(photo)
        await self._db.flush()  # get DB-generated id/created_at without committing
        await self._db.refresh(photo)
        return photo

    async def update_moderation(
        self,
        photo_id: uuid.UUID,
        status: ModerationStatusEnum,
        rejection_reason: str | None = None,
    ) -> ProfilePhoto | None:
        """Set moderation_status (and optionally rejection_reason). Admin only."""
        stmt = (
            update(ProfilePhoto)
            .where(ProfilePhoto.id == photo_id)
            .values(
                moderation_status=status,
                rejection_reason=rejection_reason,
            )
            .returning(ProfilePhoto)
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return result.scalar_one_or_none()

    async def set_primary(
        self, profile_id: uuid.UUID, photo_id: uuid.UUID
    ) -> None:
        """
        Atomically clear is_primary on all photos then set it on the given one.

        The partial unique index (WHERE is_primary = TRUE AND
        moderation_status != 'REJECTED') enforces uniqueness at the DB level;
        this two-step update is still safe because it runs in one transaction.
        """
        # Step 1: clear all primary flags for this profile
        await self._db.execute(
            update(ProfilePhoto)
            .where(ProfilePhoto.profile_id == profile_id)
            .values(is_primary=False)
        )
        # Step 2: set primary on the chosen photo
        await self._db.execute(
            update(ProfilePhoto)
            .where(ProfilePhoto.id == photo_id)
            .where(ProfilePhoto.profile_id == profile_id)
            .values(is_primary=True)
        )
        await self._db.flush()

    async def delete(self, photo_id: uuid.UUID) -> bool:
        """Hard delete one photo row. Caller must also delete Firebase objects."""
        result = await self._db.execute(
            delete(ProfilePhoto).where(ProfilePhoto.id == photo_id)
        )
        await self._db.flush()
        return result.rowcount > 0

    async def hard_delete_all_for_profile(self, profile_id: uuid.UUID) -> int:
        """Hard delete ALL photo rows for a profile (account deletion flow)."""
        result = await self._db.execute(
            delete(ProfilePhoto).where(ProfilePhoto.profile_id == profile_id)
        )
        await self._db.flush()
        return result.rowcount
