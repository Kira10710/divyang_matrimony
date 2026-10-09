"""
LoginHistory ORM model.

Append-only audit trail of authentication events.
Read for device tracking and suspicious login detection.
Session revocation does NOT operate on this table — see active_sessions.py.
See Database.md §3.16, Architecture §7.7, §5.6.

Delete strategy: Hard delete after 180 days (scheduled job). No deleted_at.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class LoginEventTypeEnum(str, enum.Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"


class LoginHistory(Base, UUIDPrimaryKeyMixin):
    """
    Immutable authentication event log.

    One row per auth event. Never updated.
    The refresh_token_jti column links this audit event to a row in active_sessions.
    """

    __tablename__ = "login_history"

    # --- Foreign key ---
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Event ---
    event_type: Mapped[LoginEventTypeEnum] = mapped_column(
        Enum(LoginEventTypeEnum, name="login_event_type_enum"),
        nullable=False,
    )

    # --- Context ---
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Parsed device model, e.g. 'Samsung Galaxy A52'",
    )

    # --- Session linkage (soft reference to active_sessions.refresh_token_jti) ---
    refresh_token_jti: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Links this audit event to a specific session row in active_sessions.",
    )

    # --- Suspicious flag ---
    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Flagged by new-device detection (§7.7). Does not block login.",
    )

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

    # --- Relationships ---
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="login_history",
        lazy="noload",
    )

    # --- Indexes (Database.md §4.3) ---
    __table_args__ = (
        Index("ix_login_history_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LoginHistory id={self.id} user_id={self.user_id} event={self.event_type}>"
