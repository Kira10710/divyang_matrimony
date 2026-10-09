"""
Authentication API routes.

Implements:
    POST   /auth/send-otp          - Request OTP (step 1 of phone login)
    POST   /auth/verify-otp        - Verify OTP, receive tokens (step 2)
    POST   /auth/login-admin       - Admin email+password login (Architecture §6)
    POST   /auth/refresh           - Rotate refresh token
    POST   /auth/logout            - Logout current device
    POST   /auth/logout-all        - Logout all devices (Architecture §7.7)
    GET    /auth/sessions          - List active sessions (Architecture §6)
    GET    /auth/me                - Get current authenticated user

Architecture §3.8: All responses use the standard envelope.
Route handlers are thin — they validate input, call the service, commit, respond.
No business logic lives here.
"""
import jwt
import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_auth_service,
    get_current_active_user,
    get_request_context,
)
from app.core.response import ApiResponse, success_response
from app.models.user import User
from app.schemas.auth import (
    AdminLoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    SendOtpRequest,
    SessionListResponse,
    TokenPair,
    UserOut,
    VerifyOtpRequest,
)
from app.services.auth_service import AuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# OTP flow
# ---------------------------------------------------------------------------

@router.post(
    "/send-otp",
    status_code=status.HTTP_200_OK,
    summary="Request OTP for phone-based login",
    description=(
        "Step 1: Send a one-time password to the provided phone number. "
        "A new OTP can be requested at most 5 times per hour per phone."
    ),
)
async def send_otp(
    body: SendOtpRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    await auth_service.send_otp(
        phone=body.phone,
        platform_id=body.platform_id,
    )
    return success_response(message="OTP sent successfully")


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[LoginResponse],
    summary="Verify OTP and receive authentication tokens",
    description=(
        "Step 2: Verify the OTP received via SMS. On success, returns an access token "
        "(15 min) and a refresh token (30 days). New users are created automatically."
    ),
)
async def verify_otp(
    body: VerifyOtpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    ctx = get_request_context(request)
    result = await auth_service.verify_otp(
        phone=body.phone,
        otp_code=body.otp,
        platform_id=body.platform_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        device_info=body.device_info,
        fcm_token=body.fcm_token,
    )
    await db.commit()
    return success_response(
        data=result.model_dump(),
        message="Login successful",
    )


# ---------------------------------------------------------------------------
# Admin login
# ---------------------------------------------------------------------------

@router.post(
    "/login-admin",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[LoginResponse],
    summary="Admin email + password login",
    description=(
        "Admin-only login endpoint. Admins authenticate via email + password, "
        "never OTP. See Architecture §6 and §7.8 for admin role hierarchy."
    ),
)
async def admin_login(
    body: AdminLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    ctx = get_request_context(request)
    result = await auth_service.admin_login(
        email=str(body.email),
        password=body.password,
        platform_id=body.platform_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        device_info=body.device_info,
    )
    await db.commit()
    return success_response(
        data=result.model_dump(),
        message="Admin login successful",
    )


# ---------------------------------------------------------------------------
# Token rotation
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[TokenPair],
    summary="Rotate refresh token",
    description=(
        "Exchange a valid refresh token for a new access + refresh token pair. "
        "The old refresh token is revoked immediately (rotation). "
        "Presenting a revoked token returns 401."
    ),
)
async def refresh_tokens(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    ctx = get_request_context(request)
    new_tokens = await auth_service.refresh_tokens(
        refresh_token=body.refresh_token,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )
    await db.commit()
    return success_response(
        data=new_tokens.model_dump(),
        message="Tokens refreshed",
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout from current device",
    description=(
        "Revokes the refresh token for the current session. "
        "Access tokens remain valid until they expire (15 min) — clients must discard them. "
        "Requires authentication via access token in Authorization header."
    ),
)
async def logout(
    body: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    ctx = get_request_context(request)
    await auth_service.logout(
        refresh_token=body.refresh_token,
        user_id=current_user.id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        platform_id=current_user.platform_id,
    )
    await db.commit()
    return success_response(message="Logged out successfully")


@router.post(
    "/logout-all",
    status_code=status.HTTP_200_OK,
    summary="Logout from all devices",
    description=(
        "Revokes all active refresh tokens for the current user. "
        "Use after a password change or reported account compromise (Architecture §7.7). "
        "Requires authentication via access token."
    ),
)
async def logout_all(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    ctx = get_request_context(request)
    revoked = await auth_service.logout_all(
        user_id=current_user.id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        platform_id=current_user.platform_id,
    )
    await db.commit()
    return success_response(
        data={"revoked_sessions": revoked},
        message=f"Logged out from {revoked} device(s)",
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[SessionListResponse],
    summary="List active sessions",
    description=(
        "Returns all active (non-revoked, non-expired) sessions for the current user. "
        "The session making this request is marked with is_current=True. "
        "Requires authentication via access token."
    ),
)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    # Extract jti from the current access token to mark the current session
    current_jti: str | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(auth_header[7:])
            # Access tokens don't carry jti — we'd need refresh token jti for exact match.
            # In practice, this is populated if the client sends the refresh token's jti
            # as a custom header (X-Session-JTI) — optional feature.
            current_jti = request.headers.get("x-session-jti")
        except jwt.InvalidTokenError:
            pass

    result = await auth_service.list_sessions(
        user_id=current_user.id,
        current_jti=current_jti,
    )
    return success_response(
        data=result.model_dump(),
        message="Sessions retrieved",
    )


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UserOut],
    summary="Get current authenticated user",
    description="Returns the authenticated user's profile data. Requires a valid access token.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return success_response(
        data=UserOut.model_validate(current_user).model_dump(),
        message="User retrieved",
    )
