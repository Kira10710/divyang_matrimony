"""
Profile completeness scoring service.

Calculates a deterministic 0–100 percentage from defined profile fields.
Used on both create and update — the score is recomputed from scratch
each time, never incrementally, to avoid drift.

Database.md §3.2: profiles < 40% completeness_score are excluded from search.

Scoring rules (documented, not arbitrary):

  REQUIRED fields (each worth equal weight within their tier):
  - first_name, last_name, gender, date_of_birth, marital_status → already
    required by ProfileCreateRequest, so these are always present.

  WEIGHTED optional fields:
  - Category weights are chosen based on matchmaking relevance:
    - Personal detail fields (high relevance to matching)
    - Location fields (affects search ranking)
    - Professional fields (moderate relevance)
    - Sensitive data fields (bonus — encourages completeness)
"""
from app.models.profile import Profile
from app.models.sensitive_profile_data import SensitiveProfileData

# ---------------------------------------------------------------------------
# Field definitions with weights
# ---------------------------------------------------------------------------

# Each tuple: (field_name, weight_points)
# Total max points = 100

# Required fields: always filled at create time → guaranteed 30 points
_REQUIRED_FIELDS: list[tuple[str, int]] = [
    ("first_name", 6),
    ("last_name", 6),
    ("gender", 6),
    ("date_of_birth", 6),
    ("marital_status", 6),
]

# Optional profile fields: up to 50 points
_OPTIONAL_PROFILE_FIELDS: list[tuple[str, int]] = [
    ("height_cm", 4),
    ("education", 5),
    ("occupation", 5),
    ("annual_income", 3),
    ("mother_tongue", 4),
    ("languages_spoken", 2),
    ("city", 5),
    ("state", 4),
    ("pincode", 2),
    ("bio", 6),
    ("disability_type", 5),
    ("country", 1),  # has a default, so almost always filled
    ("managed_by", 4),  # has a default
]

# Sensitive data fields: up to 20 points (bonus for completeness)
_SENSITIVE_FIELDS: list[tuple[str, int]] = [
    ("religion", 3),
    ("disability_percentage", 3),
    ("disability_since", 2),
    ("mobility_aid", 2),
    ("family_type", 2),
    ("family_status", 2),
    ("contact_phone", 3),
    ("whatsapp_number", 3),
]

# Sanity check: total must equal 100
_TOTAL = (
    sum(w for _, w in _REQUIRED_FIELDS)
    + sum(w for _, w in _OPTIONAL_PROFILE_FIELDS)
    + sum(w for _, w in _SENSITIVE_FIELDS)
)
assert _TOTAL == 100, f"Completeness weights must sum to 100, got {_TOTAL}"


def calculate_completeness(
    profile: Profile,
    sensitive_data: SensitiveProfileData | None = None,
) -> int:
    """
    Calculate profile completeness as a 0–100 integer.

    Deterministic: same input always produces the same output.
    No side effects — does not update the profile; the caller does that.
    """
    score = 0

    # Required fields
    for field_name, weight in _REQUIRED_FIELDS:
        value = getattr(profile, field_name, None)
        if value is not None and value != "":
            score += weight

    # Optional profile fields
    for field_name, weight in _OPTIONAL_PROFILE_FIELDS:
        value = getattr(profile, field_name, None)
        if value is not None and value != "":
            score += weight

    # Sensitive data fields (only if the row exists)
    if sensitive_data is not None:
        for field_name, weight in _SENSITIVE_FIELDS:
            value = getattr(sensitive_data, field_name, None)
            # Encrypted fields are stored as ciphertext — a non-None value
            # means the user provided data. We don't decrypt just to check
            # emptiness; the presence of ciphertext is sufficient.
            if value is not None and value != "":
                score += weight

    return min(score, 100)


def get_field_weights() -> dict[str, int]:
    """
    Return the complete field→weight mapping.

    Used by the profile creation/update documentation and any
    endpoint that needs to show which fields contribute to the score.
    """
    weights: dict[str, int] = {}
    for field, w in _REQUIRED_FIELDS:
        weights[field] = w
    for field, w in _OPTIONAL_PROFILE_FIELDS:
        weights[field] = w
    for field, w in _SENSITIVE_FIELDS:
        weights[f"sensitive.{field}"] = w
    return weights
