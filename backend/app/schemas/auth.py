"""
Auth Pydantic schemas — request validation and response serialization.

All endpoint-facing data goes through these schemas.
The ORM models are never returned directly from routes.

See Architecture §3.8 (standard response envelope),
Database.md §3.1, §3.16, §3.18.
"""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _validate_phone(phone: str) -> str:
    """
    Validate E.164 phone number format.

    Accepts: +91XXXXXXXXXX or 10-digit Indian numbers (auto-prefix +91).
    """
    cleaned = re.sub(r"\s+", "", phone)
    if re.match(r"^\+91\d{10}$", cleaned):
        return cleaned
    if re.match(r"^\d{10}$", cleaned):
        return f"+91{cleaned}"
    raise ValueError(
        "Invalid phone number. Provide a 10-digit Indian number or E.164 format (+91XXXXXXXXXX)."
    )


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SendOtpRequest(BaseModel):
    """POST /auth/send-otp — request an OTP for phone-based login/registration."""

    phone: str = Field(..., description="10-digit Indian phone or E.164 format")
    platform_id: str = Field(
        default="divyang_matrimony",
        description="Platform identifier (multi-platform support §14)",
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)


class VerifyOtpRequest(BaseModel):
    """POST /auth/verify-otp — verify OTP and receive tokens."""

    phone: str = Field(..., description="Same phone used in send-otp")
    otp: str = Field(..., min_length=4, max_length=8, description="OTP received via SMS")
    platform_id: str = Field(default="divyang_matrimony")
    fcm_token: str | None = Field(
        default=None,
        description="Firebase push token. Updated in users.fcm_token on login.",
    )
    device_info: str | None = Field(
        default=None,
        description="Device model string for session tracking (§7.7).",
        max_length=255,
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("otp")
    @classmethod
    def validate_otp_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v


class AdminLoginRequest(BaseModel):
    """POST /auth/login-admin — admin email+password login (Architecture §6)."""

    email: EmailStr = Field(..., description="Admin account email address")
    password: str = Field(..., min_length=8, description="Admin password")
    platform_id: str = Field(default="divyang_matrimony")
    device_info: str | None = Field(default=None, max_length=255)


class RefreshTokenRequest(BaseModel):
    """POST /auth/refresh — rotate refresh token."""

    refresh_token: str = Field(..., description="Current valid refresh token")


class LogoutRequest(BaseModel):
    """POST /auth/logout — logout current session."""

    refresh_token: str = Field(..., description="Refresh token of the session to terminate")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenPair(BaseModel):
    """Access + refresh token pair returned on successful auth."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    access_token_expires_in: int = Field(
        description="Access token TTL in seconds"
    )


class UserOut(BaseModel):
    """Safe user representation — no password_hash, no deleted_at."""

    id: uuid.UUID
    phone: str | None
    email: str | None
    role: str | None
    platform_id: str
    is_active: bool
    is_banned: bool
    is_phone_verified: bool
    is_email_verified: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response body for all successful login/register flows."""

    user: UserOut
    tokens: TokenPair
    is_new_user: bool = Field(
        description="True if this is the first-ever login for this phone/platform.",
        default=False,
    )


class SessionOut(BaseModel):
    """One active session row — shown in GET /auth/sessions."""

    id: uuid.UUID
    device_info: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool = Field(
        default=False,
        description="True if this session is the one making this request.",
    )

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Response for GET /auth/sessions."""

    sessions: list[SessionOut]
    total: int


class MessageResponse(BaseModel):
    """Generic success response with only a message."""

    message: str
