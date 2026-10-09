"""
ORM model registry.

Import all models here so SQLAlchemy's MetaData knows about them
for Alembic autogenerate and relationship resolution.
"""
from app.models.active_session import ActiveSession  # noqa: F401
from app.models.base import Base  # noqa: F401
from app.models.enums import (  # noqa: F401
    DisabilityTypeEnum,
    GenderEnum,
    MaritalStatusEnum,
    ModerationStatusEnum,
    ProfileManagedByEnum,
    VerificationStatusEnum,
    VisibilityTier,
)
from app.models.login_history import LoginEventTypeEnum, LoginHistory  # noqa: F401
from app.models.partner_preference import PartnerPreference  # noqa: F401
from app.models.platform_config import PlatformConfig  # noqa: F401
from app.models.profile import Profile  # noqa: F401
from app.models.profile_photo import ProfilePhoto  # noqa: F401
from app.models.sensitive_data_access_log import SensitiveDataAccessLog  # noqa: F401
from app.models.sensitive_profile_data import SensitiveProfileData  # noqa: F401
from app.models.user import AdminRoleEnum, User  # noqa: F401

__all__ = [
    "Base",
    "User",
    "AdminRoleEnum",
    "ActiveSession",
    "LoginHistory",
    "LoginEventTypeEnum",
    "Profile",
    "SensitiveProfileData",
    "PartnerPreference",
    "SensitiveDataAccessLog",
    "PlatformConfig",
    "ProfilePhoto",
    "GenderEnum",
    "MaritalStatusEnum",
    "DisabilityTypeEnum",
    "ProfileManagedByEnum",
    "VerificationStatusEnum",
    "VisibilityTier",
    "ModerationStatusEnum",
]
