"""
ActiveSession ORM model.

The mutable session/revocation store. This is the table that:
- The JWT-refresh dependency queries on every token refresh.
- GET /api/v1/auth/sessions lists (not login_history).
- POST /api/v1/auth/logout-all bulk-revokes.
- POST /api/v1/auth/logout revokes a single row.

See Database.md §3.18, Architecture §7.7.

Delete strategy: Hard delete when expired or after explicit revocation cleanup.
Rows are naturally bounded by refresh token lifetime (30 days per Architecture §4.1).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class ActiveSession(Base, UUIDPrimaryKeyMixin):
    """
    One row per issued refresh token.

    Queried on every token refresh to enforce revocation:
    1. Find row by refresh_token_jti
    2. Check is_revoked = FALSE
    3. Check expires_at > NOW()
    4. If valid, revoke old row and issue new token + new session row (rotation)
    """

    __tablename__ = "active_sessions"

    # --- Foreign key ---
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- Token identity ---
    refresh_token_jti: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="JWT jti claim — one row per issued refresh token.",
    )

    # --- Device info (shown in 'manage sessions' UI) ---
    device_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Parsed device model shown in session management UI.",
    )
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    # --- Lifetime ---
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Matches the refresh token JWT expiry (30 days, per Architecture §4.1).",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Updated on each successful token refresh.",
    )

    # --- Revocation ---
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Set TRUE on logout / logout-all / password change.",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --- Platform ---
    platform_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="divyang_matrimony",
        server_default="divyang_matrimony",
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="active_sessions",
        lazy="noload",
    )

    # --- Indexes (Database.md §4.3) ---
    __table_args__ = (
        Index("ix_active_sessions_user_id_is_revoked", "user_id", "is_revoked"),
        Index("ix_active_sessions_expires_at", "expires_at"),
        # Unique index on refresh_token_jti already covered by unique=True above
    )

    def __repr__(self) -> str:
        return (
            f"<ActiveSession id={self.id} user_id={self.user_id} "
            f"jti={self.refresh_token_jti[:8]}... revoked={self.is_revoked}>"
        )
