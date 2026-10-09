"""
Security utilities: JWT encoding/decoding, password hashing.

Architecture §7.1 + user requirement: Argon2 (not bcrypt) for admin password hashing.
Architecture §7.7: refresh tokens are enumerable and revocable via active_sessions.

Key design decisions:
- Argon2id (via argon2-cffi) replaces bcrypt — winner of the Password Hashing
  Competition, memory-hard, recommended by OWASP for new systems.
- PyJWT replaces python-jose (which is unmaintained).
- Every refresh token carries a `jti` (JWT ID) UUID — this is the key that
  active_sessions is indexed on. Without jti, individual session revocation is impossible.
- Access tokens are stateless (15 min) — verified by decoding only, no DB lookup.
- Refresh tokens are stateful (30 days) — verified by decoding + active_sessions DB check.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

# ---------------------------------------------------------------------------
# Argon2 password hasher — used ONLY for admin accounts (OTP users have no password)
# ---------------------------------------------------------------------------
# OWASP 2023 recommended Argon2id parameters:
#   - time_cost=2  (number of iterations)
#   - memory_cost=65536  (64 MB)
#   - parallelism=1
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Only called for admin account creation/password change.
    End users authenticate via OTP — they have no password.
    """
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against an Argon2id hash.

    Returns False (never raises) on mismatch or invalid hash.
    """
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    """
    Check if an Argon2 hash should be upgraded to current parameters.

    Call after a successful login and rehash transparently if True.
    """
    return _ph.check_needs_rehash(hashed_password)


# ---------------------------------------------------------------------------
# JWT — access token (stateless) + refresh token (stateful via active_sessions)
# ---------------------------------------------------------------------------

def _base_payload(user_id: uuid.UUID, platform_id: str) -> dict[str, Any]:
    """Shared fields for both token types."""
    return {
        "sub": str(user_id),     # subject = user ID
        "platform": platform_id,
    }


def create_access_token(
    user_id: uuid.UUID,
    platform_id: str,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a short-lived access token (default: 15 min).

    Access tokens are STATELESS — verified by decoding only.
    Role is embedded so the `require_role` dependency doesn't need a DB call.

    Payload:
        sub: user_id
        platform: platform_id
        role: admin role or None
        type: "access"
        exp: expiry
        iat: issued-at
    """
    now = datetime.now(UTC)
    expire = now + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = _base_payload(user_id, platform_id)
    payload.update({
        "type": "access",
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    })
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    platform_id: str,
    jti: uuid.UUID | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, uuid.UUID]:
    """
    Create a long-lived refresh token (default: 30 days).

    Returns (encoded_token, jti_uuid) — the jti must be stored in active_sessions.

    Refresh tokens are STATEFUL — validated by:
    1. JWT signature + expiry
    2. active_sessions lookup: is_revoked=False, expires_at > now

    Payload:
        sub: user_id
        platform: platform_id
        type: "refresh"
        jti: unique token ID (stored in active_sessions)
        exp: expiry
        iat: issued-at
    """
    token_jti = jti or uuid.uuid4()
    now = datetime.now(UTC)
    expire = now + (
        expires_delta or timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )
    payload = _base_payload(user_id, platform_id)
    payload.update({
        "type": "refresh",
        "jti": str(token_jti),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    })
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, token_jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token (signature + expiry only).

    Does NOT check active_sessions — that is the caller's responsibility
    for refresh tokens (see auth_service.py).

    Raises:
        jwt.ExpiredSignatureError — token has expired
        jwt.InvalidTokenError — any other JWT failure
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode an access token and assert its type is 'access'.

    Raises jwt.InvalidTokenError if type != 'access'.
    """
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """
    Decode a refresh token and assert its type is 'refresh'.

    Does NOT check active_sessions — the service layer does that.
    Raises jwt.InvalidTokenError if type != 'refresh'.
    """
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    return payload
