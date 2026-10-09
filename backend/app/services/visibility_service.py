"""
Visibility/access service — determines what tier of data a viewer can see.

Implements Database.md §6 (Data Privacy Classification):

  PUBLIC      → any logged-in user / search results
  REGISTERED  → any logged-in user viewing profile detail
  SUBSCRIBERS → users with active BASIC+ subscription
  MATCHED     → both users in a mutual interest
  PRIVATE     → profile owner + ADMIN+ admins

Enforcement is server-side only (Architecture §6 note).
The client never receives fields above the viewer's access level.
"""
from datetime import date

from app.models.enums import VisibilityTier
from app.models.profile import Profile
from app.models.user import AdminRoleEnum, User
from app.schemas.profile import ProfileOut


def resolve_visibility_tier(
    viewer: User,
    profile: Profile,
    *,
    has_active_subscription: bool = False,
    has_mutual_interest: bool = False,
) -> VisibilityTier:
    """
    Determine the highest visibility tier the viewer has for this profile.

    Args:
        viewer: The authenticated user viewing the profile.
        profile: The target profile being viewed.
        has_active_subscription: Whether the viewer has a BASIC+ subscription.
            Determined by the subscription service (not implemented in this phase).
        has_mutual_interest: Whether both users have accepted interests.
            Determined by the interest service (not implemented in this phase).

    Returns:
        The highest tier the viewer qualifies for.
    """
    # PRIVATE: owner or admin
    if viewer.id == profile.user_id:
        return VisibilityTier.PRIVATE

    if viewer.role in (AdminRoleEnum.ADMIN, AdminRoleEnum.SUPER_ADMIN):
        return VisibilityTier.PRIVATE

    # MATCHED: mutual interest
    if has_mutual_interest:
        return VisibilityTier.MATCHED

    # SUBSCRIBERS: active subscription
    if has_active_subscription:
        return VisibilityTier.SUBSCRIBERS

    # REGISTERED: any logged-in user viewing detail
    return VisibilityTier.REGISTERED


def _compute_age(dob: date) -> int:
    """Compute age from date of birth."""
    today = date.today()
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age


# ---------------------------------------------------------------------------
# Tier→fields mapping (Database.md §6)
# ---------------------------------------------------------------------------

# Fields visible at each tier (cumulative — higher tiers inherit lower)
_PUBLIC_FIELDS: set[str] = {
    "id", "user_id", "platform_id",
    "first_name", "gender", "age", "city", "state",
    "disability_type", "verification_status", "managed_by",
    "completeness_score", "is_profile_visible",
}

_REGISTERED_FIELDS: set[str] = _PUBLIC_FIELDS | {
    "last_name", "education", "occupation", "marital_status",
    "height_cm", "mother_tongue", "bio", "country",
    "languages_spoken",
}

_PRIVATE_FIELDS: set[str] = _REGISTERED_FIELDS | {
    "annual_income", "date_of_birth", "pincode",
    "created_at", "updated_at",
}

# Sensitive data fields at SUBSCRIBERS tier
_SUBSCRIBERS_SENSITIVE: set[str] = {
    "religion", "caste", "sub_caste",
    "family_type", "family_status", "father_occupation",
    "mother_occupation", "siblings",
    "disability_percentage", "disability_since", "mobility_aid",
}

# Sensitive data fields at MATCHED tier (adds contact + encrypted details)
_MATCHED_SENSITIVE: set[str] = _SUBSCRIBERS_SENSITIVE | {
    "contact_phone", "contact_email", "whatsapp_number",
    "disability_details", "health_conditions", "about_family",
}


def _tier_rank(tier: VisibilityTier) -> int:
    """Numeric rank for tier comparison."""
    return {
        VisibilityTier.PUBLIC: 0,
        VisibilityTier.REGISTERED: 1,
        VisibilityTier.SUBSCRIBERS: 2,
        VisibilityTier.MATCHED: 3,
        VisibilityTier.PRIVATE: 4,
    }[tier]


def get_allowed_profile_fields(tier: VisibilityTier) -> set[str]:
    """Return the set of profile fields visible at the given tier."""
    rank = _tier_rank(tier)
    if rank >= _tier_rank(VisibilityTier.PRIVATE):
        return _PRIVATE_FIELDS
    if rank >= _tier_rank(VisibilityTier.REGISTERED):
        return _REGISTERED_FIELDS
    return _PUBLIC_FIELDS


def get_allowed_sensitive_fields(tier: VisibilityTier) -> set[str]:
    """
    Return the set of sensitive_profile_data fields visible at the given tier.

    PUBLIC and REGISTERED tiers see NO sensitive fields.
    SUBSCRIBERS see a subset (religion, caste, disability stats, family).
    MATCHED see all sensitive fields (+ contact info).
    PRIVATE sees everything.
    """
    rank = _tier_rank(tier)
    if rank >= _tier_rank(VisibilityTier.PRIVATE):
        return _MATCHED_SENSITIVE  # owner/admin sees everything
    if rank >= _tier_rank(VisibilityTier.MATCHED):
        return _MATCHED_SENSITIVE
    if rank >= _tier_rank(VisibilityTier.SUBSCRIBERS):
        return _SUBSCRIBERS_SENSITIVE
    return set()


def filter_profile_for_tier(
    profile: Profile,
    tier: VisibilityTier,
) -> ProfileOut:
    """
    Build a ProfileOut from an ORM profile, including only the fields
    the given visibility tier allows.

    Fields not allowed are set to None in the response.
    `age` is always computed from date_of_birth (but raw dob is PRIVATE-only).
    """
    allowed = get_allowed_profile_fields(tier)
    age = _compute_age(profile.date_of_birth) if profile.date_of_birth else None

    data: dict = {
        "id": profile.id,
        "user_id": profile.user_id,
        "platform_id": profile.platform_id,
        "visibility_tier": tier,
        "age": age,
    }

    # Map profile fields, nulling out those not in the allowed set
    profile_field_names = [
        "managed_by", "first_name", "last_name", "gender", "date_of_birth",
        "marital_status", "height_cm", "education", "occupation",
        "annual_income", "mother_tongue", "languages_spoken",
        "city", "state", "country", "pincode", "bio",
        "disability_type", "completeness_score", "is_profile_visible",
        "verification_status", "created_at", "updated_at",
    ]

    for field in profile_field_names:
        if field in allowed:
            data[field] = getattr(profile, field, None)
        else:
            data[field] = None

    return ProfileOut(**data)
