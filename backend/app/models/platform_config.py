"""
PlatformConfig ORM model.

Per-platform runtime configuration (Architecture §14.2, Database.md §3.20).
Stores branding, age bounds, feature flags, and Razorpay keys per platform.

This is the table that makes `platform_id` scoping meaningful — without it,
every row's `platform_id` would exist but there'd be nowhere to define
what differs per platform.

Never deleted. Deactivate via `is_active = FALSE`.
"""
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Per-platform configuration — one row per platform.

    The `settings` JSONB column must always contain at least:
    - minimum_age (int)
    - maximum_age (int)
    - require_disability (bool)

    Everything else in `settings` is optional.
    """

    __tablename__ = "platform_config"

    platform_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Matches platform_id values elsewhere (e.g. 'divyang_matrimony').",
    )
    app_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name for branding.",
    )
    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="'{}'",
        comment="Flexible config: age bounds, feature flags, branding, etc.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="FALSE = platform disabled, not accepting new registrations.",
    )

    # --- Constraints ---
    # NOTE: The JSONB key-existence CHECK ("settings ? 'minimum_age'...") uses
    # a PostgreSQL-specific operator and cannot be expressed in SQLAlchemy's
    # ORM layer without breaking SQLite-based tests. The constraint is enforced:
    #   1) In the Alembic migration (0002_profile_tables.py) — runs on PostgreSQL only.
    #   2) In PlatformConfigService.get_settings() — validates required keys at runtime.
    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<PlatformConfig key={self.platform_key} active={self.is_active}>"

    @property
    def minimum_age(self) -> int:
        return int(self.settings.get("minimum_age", 18))

    @property
    def maximum_age(self) -> int:
        return int(self.settings.get("maximum_age", 80))

    @property
    def require_disability(self) -> bool:
        return bool(self.settings.get("require_disability", True))
