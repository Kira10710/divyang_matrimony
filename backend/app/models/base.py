"""
SQLAlchemy declarative base and common mixins.

See Architecture Section 5.5 for soft-delete strategy:
- Soft-delete mixin applied SELECTIVELY (users, profiles, sensitive_data)
- NOT a blanket base-class default
- Tables like payments and audit_logs are never deleted

All tables use UUID primary keys and UTC timestamps.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at columns.

    Applied to all tables.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Adds a deleted_at column for soft deletion.

    Applied ONLY to tables that use soft delete (Section 5.5):
    - users, profiles, sensitive_profile_data, verifications

    NOT applied to: payments, reports, audit_logs, consent_logs,
    profile_photos, notifications.
    """
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class UUIDPrimaryKeyMixin:
    """UUID primary key column — used on all tables."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
