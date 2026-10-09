"""
Generic CRUD repository base class.

Provides standard create/read/update/delete operations.
Feature-specific repositories extend this with custom queries.
"""
from datetime import UTC
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async CRUD repository."""

    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a single record by primary key."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Get paginated list of records."""
        result = await self.db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, obj_in: dict[str, Any]) -> ModelType:
        """Create a new record from a dict of field values."""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: dict[str, Any]) -> ModelType:
        """Update an existing record with a dict of field values."""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj: ModelType) -> None:
        """Hard delete a record. Use soft_delete() for soft-deletable tables."""
        await self.db.delete(db_obj)
        await self.db.flush()

    async def soft_delete(self, db_obj: ModelType) -> ModelType:
        """
        Soft delete by setting deleted_at.

        Only valid for models that include SoftDeleteMixin.
        """
        from datetime import datetime
        db_obj.deleted_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj
