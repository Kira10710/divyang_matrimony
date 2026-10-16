"""
Admin account provisioning (Architecture §7.8, Database.md §3.1).

Admins are internal staff with issued credentials; there is deliberately no
public endpoint for creating them. This service holds the rules, and
`scripts/create_admin.py` is the only caller.

Rules:
  - A platform is always required and must exist and be active. A missing
    platform is an error, never a default and never "global".
  - ADMIN and SUPPORT are scoped to that platform.
  - SUPER_ADMIN (global access) needs an explicit `allow_super_admin=True`;
    the script only passes it after two separate deliberate confirmations.
    A SUPER_ADMIN still has a home platform for login (email + platform).
  - Passwords are validated and hashed (Argon2id); they are never logged.
"""

from __future__ import annotations

import structlog
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError
from app.core.security import hash_password
from app.models.user import AdminRoleEnum, User
from app.repositories.platform_config_repository import PlatformConfigRepository
from app.repositories.user_repository import UserRepository

logger = structlog.get_logger(__name__)

MIN_ADMIN_PASSWORD_LENGTH = 12
_email_adapter = TypeAdapter(EmailStr)


def validate_admin_password(password: str) -> None:
    """Raise BadRequestError unless the password meets the admin policy."""
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise BadRequestError(f"Admin password must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise BadRequestError("Admin password must contain both letters and digits.")


async def provision_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    role: AdminRoleEnum | str,
    platform_id: str | None,
    allow_super_admin: bool = False,
) -> User:
    """Create an admin account. Flushes but does not commit; the caller commits."""
    try:
        admin_role = role if isinstance(role, AdminRoleEnum) else AdminRoleEnum(str(role).upper())
    except ValueError as exc:
        raise BadRequestError(f"Unknown admin role: {role!r}") from exc

    platform = (platform_id or "").strip()
    if not platform:
        raise BadRequestError("An explicit platform is required to provision an admin.")

    if admin_role == AdminRoleEnum.SUPER_ADMIN and not allow_super_admin:
        raise BadRequestError("Provisioning a SUPER_ADMIN requires explicit authorization.")

    try:
        normalized_email = str(_email_adapter.validate_python(email)).lower()
    except ValidationError as exc:
        raise BadRequestError("A valid email address is required.") from exc

    validate_admin_password(password)

    config = await PlatformConfigRepository(db).get_by_key(platform)
    if config is None or not config.is_active:
        raise BadRequestError(f"Platform {platform!r} does not exist or is not active.")

    users = UserRepository(db)
    if await users.get_by_email(normalized_email, platform) is not None:
        raise ConflictError("An account with this email already exists on this platform.")

    admin = await users.create(
        {
            "platform_id": platform,
            "email": normalized_email,
            "password_hash": hash_password(password),
            "role": admin_role,
            "is_active": True,
            "is_banned": False,
            "is_phone_verified": False,
            "is_email_verified": True,
        }
    )
    # No email, password or hash in the log; the id is enough to trace it.
    logger.info(
        "admin_provisioned",
        user_id=str(admin.id),
        role=admin_role.value,
        platform_id=platform,
    )
    return admin
