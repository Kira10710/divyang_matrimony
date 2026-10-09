"""
User ORM model.

Maps to the `users` table — the authentication/account table.
One row per registered user (end user or admin).
See Database.md §3.1 and Architecture §4.1, §7.7.

Soft-delete strategy: uses SoftDeleteMixin (deleted_at).
30-day cooling-off period before hard purge of PII (§5.5).
"""
# Enums matching Database.md §2
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AdminRoleEnum(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    SUPPORT = "SUPPORT"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Authentication and account table.

    Constraints (enforced at app layer, with DB uniqueness from partial indexes):
    - UNIQUE (phone, platform_id) WHERE deleted_at IS NULL
    - UNIQUE (email, platform_id) WHERE deleted_at IS NULL AND email IS NOT NULL
    - Admin accounts must have email + password_hash (no OTP path for admins)
    - End users must have phone (no email required)
    """

    __tablename__ = "users"

    # --- Platform ---
    platform_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="divyang_matrimony",
        server_default="divyang_matrimony",
    )

    # --- Identity ---
    phone: Mapped[str | None] = mapped_column(
        String(15),
        nullable=True,
        comment="E.164 format. NULL only for admin accounts without a phone.",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional for end users. Required for admin accounts.",
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="NULL for OTP users. Argon2 hash for admin accounts.",
    )

    # --- Admin role (NULL = regular user) ---
    role: Mapped[AdminRoleEnum | None] = mapped_column(
        Enum(AdminRoleEnum, name="admin_role_enum"),
        nullable=True,
        comment="NULL = end user. Set for admin accounts only (§7.8).",
    )

    # --- Account state ---
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Set by admin action. All bans are audit-logged.",
    )
    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # --- Push notifications ---
    fcm_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Firebase Cloud Messaging device token. Updated on each login.",
    )

    # --- Last activity ---
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships (declared here; circular imports avoided via string refs) ---
    active_sessions: Mapped[list["ActiveSession"]] = relationship(  # noqa: F821
        "ActiveSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    login_history: Mapped[list["LoginHistory"]] = relationship(  # noqa: F821
        "LoginHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # --- DB-level uniqueness (partial) ---
    __table_args__ = (
        UniqueConstraint(
            "phone",
            "platform_id",
            name="uq_users_phone_platform_active",
            # Note: partial WHERE clause (deleted_at IS NULL) cannot be expressed
            # directly in SQLAlchemy's UniqueConstraint — enforced in the Alembic
            # migration as a raw SQL partial index.
            # See: backend/alembic/versions/... partial index migration.
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"

    @property
    def is_admin(self) -> bool:
        """True if this user has any admin role."""
        return self.role is not None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
