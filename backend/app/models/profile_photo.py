"""
ProfilePhoto ORM model.

Stores Firebase Storage object *paths* (not URLs) for three image variants:
  - storage_path  : original compressed image (~1600px) — PRIVATE tier only
  - medium_path   : 800px variant for profile detail view — REGISTERED+
  - thumbnail_path: 200px variant for search results — PUBLIC

Resizing is done client-side (Architecture §4.2). The server validates
type/size, strips EXIF/GPS, and moderates all three variants before any
are served. Signed read URLs are issued per-request after the viewer's
privacy-tier check; long-lived Firebase download URLs are never used
(Database.md §3.4, §6).

Hard delete — no deleted_at column (Database.md §5.5).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, SmallInteger, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import ModerationStatusEnum


class ProfilePhoto(Base, UUIDPrimaryKeyMixin):
    """
    One photo (three variants) belonging to a profile.

    Database.md §3.4. Photos are immutable after upload — replaced via
    delete + re-upload, so only created_at is needed (no updated_at).
    """

    __tablename__ = "profile_photos"

    # --- Timestamps (created_at only — photos are immutable) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # --- FK ---
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ForeignKey defined via __table_args__ DDL in migration to avoid
        # circular import with Profile model; relationship still wired below.
        nullable=False,
        index=True,
        comment="FK -> profiles.id ON DELETE CASCADE",
    )

    # --- Firebase Storage object paths (never download URLs) ---
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Firebase Storage path of original (~1600px). PRIVATE tier only.",
    )
    medium_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Firebase Storage path of 800px variant. REGISTERED+ tier.",
    )
    thumbnail_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Firebase Storage path of 200px variant. PUBLIC tier.",
    )

    # --- Ordering ---
    display_order: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Sort order; 0 = primary display position.",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Exactly one APPROVED primary photo per profile.",
    )

    # --- Moderation ---
    moderation_status: Mapped[ModerationStatusEnum] = mapped_column(
        SAEnum(ModerationStatusEnum, name="moderation_status_enum", create_type=False),
        nullable=False,
        default=ModerationStatusEnum.PENDING,
        server_default="PENDING",
        index=True,
        comment="Admin moderation state. Photos shown only when APPROVED.",
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Set by admin when moderation_status = REJECTED.",
    )

    # --- Constraints / Indexes ---
    # The partial unique index for is_primary is created in the Alembic migration:
    #   CREATE UNIQUE INDEX uq_profile_photos_primary
    #   ON profile_photos(profile_id)
    #   WHERE is_primary = TRUE AND moderation_status != 'REJECTED';
    #
    # Max 6 photos per profile enforced in PhotoService, not DB (§3.4).
    __table_args__ = ()

    def __repr__(self) -> str:
        return (
            f"<ProfilePhoto id={self.id} profile={self.profile_id} "
            f"primary={self.is_primary} status={self.moderation_status}>"
        )
