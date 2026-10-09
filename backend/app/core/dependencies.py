"""
FastAPI dependency factories.

These are injected via Depends() into route handlers.
See Architecture Section 3.3 for the dependency graph:

    Route Handler
      -> Depends(get_current_user)       -> JWT decode + active_sessions DB check
      -> Depends(get_current_active_user) -> checks is_active, is_banned
      -> Depends(require_role(...))       -> checks role from token payload
      -> Depends(service)                -> Depends(repository) -> Depends(get_db)

Key: get_current_user validates the ACCESS token (stateless).
     Refresh endpoints validate the REFRESH token via active_sessions (stateful).
     The separation keeps normal API calls fast (no DB hit for auth).
"""
import uuid

import jwt
import redis.asyncio as aioredis
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    AccountBannedError,
    ForbiddenError,
    InvalidTokenError,
    TokenExpiredError,
    UnauthorizedError,
)
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.models.user import AdminRoleEnum, User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.otp_service import ConsoleOtpService, IOtpService, RedisOtpService

logger = structlog.get_logger(__name__)
security_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Infrastructure dependencies
# ---------------------------------------------------------------------------


async def get_otp_service(
    redis: aioredis.Redis = Depends(get_redis),
) -> IOtpService:
    """
    Provide the appropriate OTP service implementation.

    Development: ConsoleOtpService (prints to stdout, no Redis needed for OTP).
    Production/Staging: RedisOtpService (real Redis TTL storage + SMS delivery).
    """
    if settings.ENVIRONMENT == "development":
        return ConsoleOtpService()
    return RedisOtpService(redis)


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """Provide a UserRepository instance scoped to the current request/session."""
    return UserRepository(db)


def get_session_repository(db: AsyncSession = Depends(get_db)) -> SessionRepository:
    """Provide a SessionRepository instance scoped to the current request/session."""
    return SessionRepository(db)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    otp_service: IOtpService = Depends(get_otp_service),
) -> AuthService:
    """Provide an AuthService with all dependencies injected."""
    return AuthService(user_repo, session_repo, otp_service)


# ---------------------------------------------------------------------------
# Auth dependencies — used by protected routes
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT access token from the Authorization header.

    Access tokens are STATELESS — we only decode and verify the signature.
    No DB hit. This keeps all normal API calls fast.

    Raises:
        UnauthorizedError — missing or invalid token
        TokenExpiredError — token has expired
        InvalidTokenError — malformed token
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Authorization header required")

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        raise InvalidTokenError()

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenError("Token missing subject claim")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise InvalidTokenError("Invalid user ID in token")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Extends get_current_user — checks is_active and is_banned.

    All protected endpoints use this rather than get_current_user directly.
    """
    if user := current_user:
        if not user.is_active:
            raise UnauthorizedError("Account is inactive")
        if user.is_banned:
            raise AccountBannedError()
    return current_user


def require_role(*roles: AdminRoleEnum):
    """
    Parameterized dependency that checks the user's admin role.

    Usage:
        @router.get("/admin/...")
        async def admin_endpoint(
            user: User = Depends(require_role(AdminRoleEnum.ADMIN, AdminRoleEnum.SUPER_ADMIN))
        ):

    Architecture §7.8: 3-tier admin roles.
    The role is embedded in the JWT access token payload — no DB hit required.
    """
    async def _role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in roles:
            raise ForbiddenError(
                f"This endpoint requires one of: {[r.value for r in roles]}"
            )
        return current_user

    return _role_checker


def require_super_admin():
    """Convenience: require SUPER_ADMIN role."""
    return require_role(AdminRoleEnum.SUPER_ADMIN)


def require_admin_or_above():
    """Convenience: require ADMIN or SUPER_ADMIN role."""
    return require_role(AdminRoleEnum.ADMIN, AdminRoleEnum.SUPER_ADMIN)


def require_any_admin():
    """Convenience: require any admin role (SUPPORT, ADMIN, SUPER_ADMIN)."""
    return require_role(
        AdminRoleEnum.SUPPORT, AdminRoleEnum.ADMIN, AdminRoleEnum.SUPER_ADMIN
    )


def get_request_context(request: Request) -> dict:
    """
    Extract common request metadata for logging and session tracking.

    Returns a dict with ip_address, user_agent.
    """
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


# ---------------------------------------------------------------------------
# Profile module dependencies
# ---------------------------------------------------------------------------

def get_profile_repository(db: AsyncSession = Depends(get_db)):
    from app.repositories.profile_repository import ProfileRepository
    return ProfileRepository(db)


def get_sensitive_data_repository(db: AsyncSession = Depends(get_db)):
    from app.repositories.sensitive_data_repository import SensitiveDataRepository
    return SensitiveDataRepository(db)


def get_partner_preference_repository(db: AsyncSession = Depends(get_db)):
    from app.repositories.partner_preference_repository import PartnerPreferenceRepository
    return PartnerPreferenceRepository(db)


def get_platform_config_repository(db: AsyncSession = Depends(get_db)):
    from app.repositories.platform_config_repository import PlatformConfigRepository
    return PlatformConfigRepository(db)


def get_platform_config_service(
    config_repo=Depends(get_platform_config_repository),
):
    from app.services.platform_config_service import PlatformConfigService
    return PlatformConfigService(config_repo)


def get_sensitive_data_service(
    sensitive_repo=Depends(get_sensitive_data_repository),
):
    from app.services.sensitive_data_service import SensitiveDataService
    return SensitiveDataService(sensitive_repo)


def get_profile_service(
    profile_repo=Depends(get_profile_repository),
    sensitive_svc=Depends(get_sensitive_data_service),
    platform_svc=Depends(get_platform_config_service),
):
    from app.services.profile_service import ProfileService
    return ProfileService(profile_repo, sensitive_svc, platform_svc)


def get_partner_preference_service(
    pref_repo=Depends(get_partner_preference_repository),
    platform_svc=Depends(get_platform_config_service),
):
    from app.services.partner_preference_service import PartnerPreferenceService
    return PartnerPreferenceService(pref_repo, platform_svc)


# ---------------------------------------------------------------------------
# Photo module dependencies
# ---------------------------------------------------------------------------

def get_photo_repository(db: AsyncSession = Depends(get_db)):
    from app.repositories.photo_repository import PhotoRepository
    return PhotoRepository(db)


def get_photo_service(
    photo_repo=Depends(get_photo_repository),
):
    from app.services.photo_service import PhotoService
    # bucket_factory and gcs_credentials_factory default to real Firebase
    # helpers inside PhotoService.__init__; override in tests via DI.
    return PhotoService(photo_repo)
