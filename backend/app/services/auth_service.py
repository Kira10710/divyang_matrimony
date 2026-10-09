"""
AuthService — core authentication business logic.

This is the only place auth business rules live. It:
- Orchestrates OTP flow (send → verify → issue tokens)
- Orchestrates admin email+password login
- Handles refresh token rotation (revoke old, issue new, create new session row)
- Implements logout (single device and all devices)
- Logs every auth event to login_history
- Detects suspicious logins (new device)

Transactions: the service flushes via repositories and commits once at the end
of each operation. Routes call db.commit() after the service method returns —
the service never commits itself (single responsibility, testability).

See Architecture §4.1, §7.7.
"""
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import structlog

from app.core.config import settings
from app.core.exceptions import (
    AccountBannedError,
    AccountLockedError,
    InvalidTokenError,
    OtpError,
    TokenExpiredError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.login_history import LoginEventTypeEnum
from app.models.user import User
from app.repositories.session_repository import ISessionRepository
from app.repositories.user_repository import IUserRepository
from app.schemas.auth import (
    LoginResponse,
    SessionListResponse,
    SessionOut,
    TokenPair,
    UserOut,
)
from app.services.otp_service import IOtpService

logger = structlog.get_logger(__name__)


def _build_token_pair(user: User) -> tuple[TokenPair, uuid.UUID]:
    """
    Create an access token + refresh token for a user.

    Returns (TokenPair, jti_uuid) — jti must be stored in active_sessions.
    """
    access_token = create_access_token(
        user_id=user.id,
        platform_id=user.platform_id,
        role=user.role.value if user.role else None,
    )
    refresh_token, jti = create_refresh_token(
        user_id=user.id,
        platform_id=user.platform_id,
    )
    token_pair = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return token_pair, jti


class AuthService:
    """
    Authentication service.

    Constructor injection: repositories and OTP service are injected,
    keeping this class fully testable without a real DB or Redis.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        session_repo: ISessionRepository,
        otp_service: IOtpService,
    ):
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._otp_service = otp_service

    # -----------------------------------------------------------------------
    # OTP flow
    # -----------------------------------------------------------------------

    async def send_otp(self, phone: str, platform_id: str) -> None:
        """
        Step 1 of phone login: generate and send an OTP.

        Does NOT create a user — user creation happens in verify_otp on first use.
        Rate limit and lockout are enforced inside otp_service.send_otp().
        """
        # Check if the account exists and is banned/inactive
        user = await self._user_repo.get_by_phone(phone, platform_id)
        if user and user.is_banned:
            raise AccountBannedError()

        # Delegate rate-limiting and delivery to OTP service
        await self._otp_service.send_otp(phone, platform_id)
        logger.info("otp_sent", phone_suffix=phone[-4:], platform_id=platform_id)

    async def verify_otp(
        self,
        phone: str,
        otp_code: str,
        platform_id: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_info: str | None = None,
        fcm_token: str | None = None,
    ) -> LoginResponse:
        """
        Step 2 of phone login: verify OTP, upsert user, issue tokens.

        - New user: create unverified user → verify → issue tokens
        - Existing user: verify → issue tokens
        - Wrong OTP: log LOGIN_FAILED, raise OtpError
        - Account locked: raise AccountLockedError
        """
        # Check account lockout (Architecture §7.7)
        if isinstance(self._otp_service, __import__("app.services.otp_service", fromlist=["RedisOtpService"]).RedisOtpService):
            if await self._otp_service.is_account_locked(phone, platform_id):  # type: ignore[attr-defined]
                raise AccountLockedError()

        is_valid = await self._otp_service.verify_otp(phone, otp_code, platform_id)

        if not is_valid:
            # Log failure if user exists
            user = await self._user_repo.get_by_phone(phone, platform_id)
            if user:
                await self._session_repo.log_event(
                    user_id=user.id,
                    event_type=LoginEventTypeEnum.LOGIN_FAILED,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    device_info=device_info,
                    refresh_token_jti=None,
                    is_suspicious=False,
                    platform_id=platform_id,
                )
                # Increment account-level failure counter
                if hasattr(self._otp_service, "record_failed_attempt"):
                    await self._otp_service.record_failed_attempt(phone, platform_id)  # type: ignore[attr-defined]
            raise OtpError()

        # OTP is valid — invalidate it immediately (one-time use)
        await self._otp_service.invalidate_otp(phone, platform_id)

        # Upsert user
        is_new_user = False
        user = await self._user_repo.get_by_phone(phone, platform_id)
        if user is None:
            user = await self._user_repo.create({
                "phone": phone,
                "platform_id": platform_id,
                "is_phone_verified": True,
                "is_active": True,
                "is_banned": False,
            })
            is_new_user = True
        else:
            if user.is_banned:
                raise AccountBannedError()
            if not user.is_active:
                raise UnauthorizedError("Account is inactive")
            if not user.is_phone_verified:
                await self._user_repo.update_phone_verified(user)

        # Issue tokens and create session
        token_pair, jti = _build_token_pair(user)
        session_expires_at = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )

        # Detect suspicious login (new device — Architecture §7.7 basic check)
        existing_sessions = await self._session_repo.list_active_sessions(user.id)
        known_devices = {s.device_info for s in existing_sessions if s.device_info}
        is_suspicious = (
            device_info is not None
            and bool(known_devices)
            and device_info not in known_devices
        )

        await self._session_repo.create_session(
            user_id=user.id,
            refresh_token_jti=str(jti),
            expires_at=session_expires_at,
            device_info=device_info,
            ip_address=ip_address,
            platform_id=platform_id,
        )

        # Update last login and FCM token
        await self._user_repo.update_last_login(user, fcm_token=fcm_token)

        # Clear failure counters on success
        if hasattr(self._otp_service, "clear_failed_attempts"):
            await self._otp_service.clear_failed_attempts(phone, platform_id)  # type: ignore[attr-defined]

        # Log success
        await self._session_repo.log_event(
            user_id=user.id,
            event_type=LoginEventTypeEnum.LOGIN_SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            refresh_token_jti=str(jti),
            is_suspicious=is_suspicious,
            platform_id=platform_id,
        )

        logger.info(
            "user_logged_in",
            user_id=str(user.id),
            is_new=is_new_user,
            is_suspicious=is_suspicious,
        )

        return LoginResponse(
            user=UserOut.model_validate(user),
            tokens=token_pair,
            is_new_user=is_new_user,
        )

    # -----------------------------------------------------------------------
    # Admin login
    # -----------------------------------------------------------------------

    async def admin_login(
        self,
        email: str,
        password: str,
        platform_id: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_info: str | None = None,
    ) -> LoginResponse:
        """
        Admin email + password login (Architecture §6).

        Separate from OTP flow — admins never use OTP.
        Same session + login_history infrastructure applies.
        """
        user = await self._user_repo.get_by_email(email, platform_id)

        async def _fail(user_id: uuid.UUID | None = None) -> None:
            """Log failure and raise consistent error (timing-attack resistant)."""
            if user_id:
                await self._session_repo.log_event(
                    user_id=user_id,
                    event_type=LoginEventTypeEnum.LOGIN_FAILED,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    device_info=device_info,
                    refresh_token_jti=None,
                    is_suspicious=False,
                    platform_id=platform_id,
                )
            raise UnauthorizedError("Invalid email or password")

        if user is None or not user.is_admin:
            # Always verify a dummy hash to prevent timing attacks
            verify_password(password, hash_password("dummy_constant_cost"))
            await _fail()

        assert user is not None  # narrowing for type checker

        if not verify_password(password, user.password_hash or ""):
            await _fail(user.id)

        if user.is_banned:
            raise AccountBannedError()
        if not user.is_active:
            raise UnauthorizedError("Admin account is inactive")

        # Rehash if needed (Argon2 parameter upgrade)
        if password_needs_rehash(user.password_hash or ""):
            await self._user_repo.update_last_login(user)  # trigger ORM load; actual rehash in user update
            # Note: rehash update is outside auth service scope — do in profile update endpoint

        token_pair, jti = _build_token_pair(user)
        session_expires_at = datetime.now(UTC) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self._session_repo.create_session(
            user_id=user.id,
            refresh_token_jti=str(jti),
            expires_at=session_expires_at,
            device_info=device_info,
            ip_address=ip_address,
            platform_id=platform_id,
        )
        await self._user_repo.update_last_login(user)

        await self._session_repo.log_event(
            user_id=user.id,
            event_type=LoginEventTypeEnum.LOGIN_SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            refresh_token_jti=str(jti),
            is_suspicious=False,
            platform_id=platform_id,
        )

        logger.info("admin_logged_in", user_id=str(user.id), role=str(user.role))

        return LoginResponse(
            user=UserOut.model_validate(user),
            tokens=token_pair,
            is_new_user=False,
        )

    # -----------------------------------------------------------------------
    # Token rotation
    # -----------------------------------------------------------------------

    async def refresh_tokens(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        """
        Rotate refresh token (Architecture §7.7 session management).

        Process:
        1. Decode JWT (signature + expiry)
        2. Look up jti in active_sessions
        3. Confirm is_revoked=False and expires_at > now
        4. Revoke old session row
        5. Issue new access + refresh token
        6. Create new session row with new jti
        7. Log TOKEN_REFRESH event

        If the jti is already revoked, it may indicate token theft — the
        caller can optionally trigger a logout-all (not done automatically
        in v1, but the session row having is_revoked=True is detectable).
        """
        try:
            payload = decode_refresh_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidTokenError:
            raise InvalidTokenError()

        jti = payload.get("jti")
        user_id_str = payload.get("sub")
        if not jti or not user_id_str:
            raise InvalidTokenError()

        # Verify session exists and is valid
        session = await self._session_repo.get_session_by_jti(jti)
        if session is None:
            raise InvalidTokenError("Session not found")
        if session.is_revoked:
            raise InvalidTokenError("Session has been revoked")
        now = datetime.now(UTC)
        if session.expires_at < now:
            raise TokenExpiredError()

        user_id = uuid.UUID(user_id_str)
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.is_banned or not user.is_active:
            raise UnauthorizedError()

        # Revoke old session and issue new one
        await self._session_repo.revoke_session(session)

        new_token_pair, new_jti = _build_token_pair(user)
        session_expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        await self._session_repo.create_session(
            user_id=user.id,
            refresh_token_jti=str(new_jti),
            expires_at=session_expires_at,
            device_info=session.device_info,
            ip_address=ip_address or session.ip_address,
            platform_id=session.platform_id,
        )

        await self._session_repo.log_event(
            user_id=user.id,
            event_type=LoginEventTypeEnum.TOKEN_REFRESH,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=session.device_info,
            refresh_token_jti=str(new_jti),
            is_suspicious=False,
            platform_id=session.platform_id,
        )

        return new_token_pair

    # -----------------------------------------------------------------------
    # Logout
    # -----------------------------------------------------------------------

    async def logout(
        self,
        refresh_token: str,
        *,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
        platform_id: str = "divyang_matrimony",
    ) -> None:
        """
        Logout from current device.

        Revokes the specific session identified by the refresh token's jti.
        Access tokens remain valid until they expire (15 min) — intentional
        for a stateless access token model. Clients should discard them.
        """
        try:
            payload = decode_refresh_token(refresh_token)
        except jwt.InvalidTokenError:
            raise InvalidTokenError()

        jti = payload.get("jti")
        if not jti:
            raise InvalidTokenError()

        session = await self._session_repo.get_session_by_jti(jti)
        if session and not session.is_revoked:
            await self._session_repo.revoke_session(session)

        await self._session_repo.log_event(
            user_id=user_id,
            event_type=LoginEventTypeEnum.LOGOUT,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=session.device_info if session else None,
            refresh_token_jti=jti,
            is_suspicious=False,
            platform_id=platform_id,
        )

        logger.info("user_logged_out", user_id=str(user_id))

    async def logout_all(
        self,
        user_id: uuid.UUID,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        platform_id: str = "divyang_matrimony",
    ) -> int:
        """
        Logout from all devices.

        Revokes every active session for the user.
        Returns the count of revoked sessions.
        Used after password change or reported account compromise (Architecture §7.7).
        """
        revoked_count = await self._session_repo.revoke_all_sessions(user_id)

        await self._session_repo.log_event(
            user_id=user_id,
            event_type=LoginEventTypeEnum.LOGOUT,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=None,
            refresh_token_jti=None,
            is_suspicious=False,
            platform_id=platform_id,
        )

        logger.info(
            "user_logged_out_all",
            user_id=str(user_id),
            revoked_sessions=revoked_count,
        )
        return revoked_count

    # -----------------------------------------------------------------------
    # Session listing
    # -----------------------------------------------------------------------

    async def list_sessions(
        self, user_id: uuid.UUID, current_jti: str | None = None
    ) -> SessionListResponse:
        """
        List all active sessions for a user.

        GET /auth/sessions — marks the session making this request as is_current=True.
        """
        sessions = await self._session_repo.list_active_sessions(user_id)
        session_out = [
            SessionOut(
                id=s.id,
                device_info=s.device_info,
                ip_address=str(s.ip_address) if s.ip_address else None,
                created_at=s.created_at,
                last_used_at=s.last_used_at,
                expires_at=s.expires_at,
                is_current=(s.refresh_token_jti == current_jti),
            )
            for s in sessions
        ]
        return SessionListResponse(sessions=session_out, total=len(session_out))
