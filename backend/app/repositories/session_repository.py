"""
SessionRepository — manages active_sessions (revocation store) and login_history (audit log).

Two separate concerns, one repository file — both are always used together
in the auth flow and have no independent use cases outside auth.

See Database.md §3.16 (login_history), §3.18 (active_sessions),
Architecture §7.7.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.active_session import ActiveSession
from app.models.login_history import LoginEventTypeEnum, LoginHistory

# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------

class ISessionRepository(ABC):
    """Abstract interface for session + login-history operations."""

    @abstractmethod
    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_jti: str,
        expires_at: datetime,
        device_info: str | None,
        ip_address: str | None,
        platform_id: str,
    ) -> ActiveSession:
        """Create a new active session row for an issued refresh token."""
        ...

    @abstractmethod
    async def get_session_by_jti(self, jti: str) -> ActiveSession | None:
        """Find session by refresh_token_jti (used on every refresh request)."""
        ...

    @abstractmethod
    async def revoke_session(self, session: ActiveSession) -> None:
        """Mark a single session as revoked (single-device logout)."""
        ...

    @abstractmethod
    async def revoke_all_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke all non-expired sessions for a user (logout-all)."""
        ...

    @abstractmethod
    async def touch_session(self, session: ActiveSession) -> None:
        """Update last_used_at on a session (called on successful token refresh)."""
        ...

    @abstractmethod
    async def list_active_sessions(self, user_id: uuid.UUID) -> list[ActiveSession]:
        """Return all non-revoked, non-expired sessions for a user (GET /auth/sessions)."""
        ...

    @abstractmethod
    async def log_event(
        self,
        *,
        user_id: uuid.UUID,
        event_type: LoginEventTypeEnum,
        ip_address: str | None,
        user_agent: str | None,
        device_info: str | None,
        refresh_token_jti: str | None,
        is_suspicious: bool,
        platform_id: str,
    ) -> LoginHistory:
        """Append an immutable login event row."""
        ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

class SessionRepository(ISessionRepository):
    """Concrete async SQLAlchemy session + login history repository."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_jti: str,
        expires_at: datetime,
        device_info: str | None,
        ip_address: str | None,
        platform_id: str,
    ) -> ActiveSession:
        now = datetime.now(UTC)
        session = ActiveSession(
            user_id=user_id,
            refresh_token_jti=refresh_token_jti,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            platform_id=platform_id,
            is_revoked=False,
            created_at=now,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_session_by_jti(self, jti: str) -> ActiveSession | None:
        """
        Lookup session by JTI — this is the critical path for every token refresh.

        Returns None if not found (never raises).
        """
        result = await self.db.execute(
            select(ActiveSession).where(ActiveSession.refresh_token_jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session: ActiveSession) -> None:
        """Single-device logout — mark one session row revoked."""
        now = datetime.now(UTC)
        session.is_revoked = True
        session.revoked_at = now
        await self.db.flush()

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> int:
        """
        Logout from all devices (Architecture §7.7).

        Bulk-updates all non-revoked sessions for this user.
        Returns count of revoked sessions.
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            update(ActiveSession)
            .where(
                and_(
                    ActiveSession.user_id == user_id,
                    ActiveSession.is_revoked.is_(False),
                    ActiveSession.expires_at > now,
                )
            )
            .values(is_revoked=True, revoked_at=now)
        )
        await self.db.flush()
        return result.rowcount  # type: ignore[return-value]

    async def touch_session(self, session: ActiveSession) -> None:
        """Update last_used_at on a session after a successful token rotation."""
        session.last_used_at = datetime.now(UTC)
        await self.db.flush()

    async def list_active_sessions(self, user_id: uuid.UUID) -> list[ActiveSession]:
        """
        List all valid (non-revoked, non-expired) sessions for a user.

        Used by GET /auth/sessions.
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ActiveSession)
            .where(
                and_(
                    ActiveSession.user_id == user_id,
                    ActiveSession.is_revoked.is_(False),
                    ActiveSession.expires_at > now,
                )
            )
            .order_by(ActiveSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def log_event(
        self,
        *,
        user_id: uuid.UUID,
        event_type: LoginEventTypeEnum,
        ip_address: str | None,
        user_agent: str | None,
        device_info: str | None,
        refresh_token_jti: str | None,
        is_suspicious: bool,
        platform_id: str,
    ) -> LoginHistory:
        """
        Append an immutable login_history row.

        Called for every auth event (success, failure, logout, refresh).
        Never updates existing rows — login_history is append-only.
        """
        entry = LoginHistory(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            refresh_token_jti=refresh_token_jti,
            is_suspicious=is_suspicious,
            platform_id=platform_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry
