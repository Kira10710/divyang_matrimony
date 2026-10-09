"""
SensitiveDataAccessLog ORM model.

Logs reads of sensitive profile fields (Architecture §5.2, §5.6).
Only logs MATCHED/SUBSCRIBERS/PRIVATE-tier field access — NOT the
PUBLIC-tier `disability_type` shown in every search result.

See Database.md §3.15.

Append-only — never updated or deleted.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class SensitiveDataAccessLog(Base, UUIDPrimaryKeyMixin):
    """
    Immutable audit log for sensitive data reads.

    One row per access event. Never updated.
    Volume control: does NOT log reads of disability_type (PUBLIC tier).
    """

    __tablename__ = "sensitive_data_access_logs"

    # --- Who viewed ---
    accessor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="Who viewed the data. No ON DELETE CASCADE — retained after user deletion.",
    )

    # --- Whose data ---
    target_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id"),
        nullable=False,
        comment="Whose data was viewed.",
    )

    # --- What was accessed ---
    fields_accessed: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        comment="Array of field names accessed (e.g. ['contact_phone', 'religion']).",
    )

    # --- At what tier ---
    access_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'MATCHED' / 'SUBSCRIBERS' / 'PRIVATE'.",
    )

    # --- Context ---
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    # --- Platform ---
    platform_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="divyang_matrimony",
        server_default="divyang_matrimony",
    )

    # --- Immutable timestamp ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # --- Indexes ---
    __table_args__ = (
        Index(
            "ix_sensitive_data_access_logs_accessor_created",
            "accessor_user_id",
            "created_at",
        ),
        Index(
            "ix_sensitive_data_access_logs_target_created",
            "target_profile_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SensitiveDataAccessLog accessor={self.accessor_user_id} "
            f"target={self.target_profile_id} tier={self.access_tier}>"
        )
