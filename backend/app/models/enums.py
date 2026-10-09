"""
Profile-domain enum types.

Maps to Database.md §2 PostgreSQL enum types.
Each enum is defined once here and imported by models, schemas, and services.
"""
import enum


class GenderEnum(enum.StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class ProfileManagedByEnum(enum.StrEnum):
    SELF = "SELF"
    PARENT = "PARENT"
    SIBLING = "SIBLING"
    GUARDIAN = "GUARDIAN"


class DisabilityTypeEnum(enum.StrEnum):
    PHYSICAL = "PHYSICAL"
    VISUAL = "VISUAL"
    HEARING = "HEARING"
    INTELLECTUAL = "INTELLECTUAL"
    MULTIPLE = "MULTIPLE"


class MaritalStatusEnum(enum.StrEnum):
    NEVER_MARRIED = "NEVER_MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    SEPARATED = "SEPARATED"


class VerificationStatusEnum(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VisibilityTier(enum.StrEnum):
    """
    Data visibility tiers — Database.md §6.

    Ordered from least to most restrictive.
    A viewer at tier N can see all fields from tiers <= N.
    """
    PUBLIC = "PUBLIC"
    REGISTERED = "REGISTERED"
    SUBSCRIBERS = "SUBSCRIBERS"
    MATCHED = "MATCHED"
    PRIVATE = "PRIVATE"


class ModerationStatusEnum(enum.StrEnum):
    """Photo moderation state — Database.md §2, §3.4, §10."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
