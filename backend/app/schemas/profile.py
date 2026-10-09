"""
Profile Pydantic schemas — request validation and response serialization.

All endpoint-facing data goes through these schemas.
ORM models are never returned directly from API endpoints.

Visibility-tier field filtering is handled by the service layer —
these schemas define what *could* be returned; the service populates
only the fields the viewer is allowed to see.

See Architecture §3.8 (response envelope), Database.md §3.2–§3.5, §6.
"""
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    DisabilityTypeEnum,
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
    VerificationStatusEnum,
    VisibilityTier,
)
from app.schemas.photo import PhotoOut

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _validate_bio_length(v: str | None) -> str | None:
    if v is not None and len(v) > 500:
        raise ValueError("Bio must be 500 characters or fewer")
    return v


# ---------------------------------------------------------------------------
# Request schemas — Profile
# ---------------------------------------------------------------------------

class ProfileCreateRequest(BaseModel):
    """POST /profiles — create a profile for the authenticated user."""

    managed_by: ProfileManagedByEnum = Field(default=ProfileManagedByEnum.SELF)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: GenderEnum
    date_of_birth: date
    marital_status: MaritalStatusEnum

    # Optional fields
    height_cm: int | None = Field(default=None, ge=50, le=300)
    education: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=200)
    annual_income: str | None = Field(default=None, max_length=100)
    mother_tongue: str | None = Field(default=None, max_length=50)
    languages_spoken: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(default="India", max_length=50)
    pincode: str | None = Field(default=None, max_length=10)
    bio: str | None = Field(default=None)
    disability_type: DisabilityTypeEnum | None = None
    is_profile_visible: bool = True

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v: str | None) -> str | None:
        return _validate_bio_length(v)


class ProfileUpdateRequest(BaseModel):
    """PATCH /profiles/me — update the authenticated user's profile."""

    managed_by: ProfileManagedByEnum | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    marital_status: MaritalStatusEnum | None = None
    height_cm: int | None = Field(default=None, ge=50, le=300)
    education: str | None = Field(default=None, max_length=200)
    occupation: str | None = Field(default=None, max_length=200)
    annual_income: str | None = Field(default=None, max_length=100)
    mother_tongue: str | None = Field(default=None, max_length=50)
    languages_spoken: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=50)
    pincode: str | None = Field(default=None, max_length=10)
    bio: str | None = None
    disability_type: DisabilityTypeEnum | None = None
    is_profile_visible: bool | None = None

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v: str | None) -> str | None:
        return _validate_bio_length(v)


# ---------------------------------------------------------------------------
# Request schemas — Sensitive Profile Data
# ---------------------------------------------------------------------------

class SensitiveDataUpdateRequest(BaseModel):
    """PUT /profiles/me/sensitive — update sensitive profile fields."""

    disability_percentage: int | None = Field(default=None, ge=0, le=100)
    disability_details: str | None = None
    disability_since: str | None = Field(default=None, max_length=50)
    mobility_aid: str | None = Field(default=None, max_length=200)
    health_conditions: str | None = None
    religion: str | None = Field(default=None, max_length=100)
    caste: str | None = Field(default=None, max_length=100)
    sub_caste: str | None = Field(default=None, max_length=100)
    family_type: str | None = Field(default=None, max_length=50)
    family_status: str | None = Field(default=None, max_length=50)
    father_occupation: str | None = Field(default=None, max_length=200)
    mother_occupation: str | None = Field(default=None, max_length=200)
    siblings: str | None = Field(default=None, max_length=200)
    about_family: str | None = None
    contact_phone: str | None = Field(default=None, max_length=15)
    contact_email: str | None = Field(default=None, max_length=255)
    whatsapp_number: str | None = Field(default=None, max_length=15)


# ---------------------------------------------------------------------------
# Request schemas — Partner Preferences
# ---------------------------------------------------------------------------

class PartnerPreferenceUpdateRequest(BaseModel):
    """PUT /profiles/me/preferences — update partner preferences."""

    preferred_gender: GenderEnum | None = None
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)
    preferred_height_min_cm: int | None = Field(default=None, ge=50, le=300)
    preferred_height_max_cm: int | None = Field(default=None, ge=50, le=300)
    preferred_marital_statuses: list[MaritalStatusEnum] | None = None
    preferred_disability_types: list[DisabilityTypeEnum] | None = None
    preferred_education: str | None = Field(default=None, max_length=200)
    preferred_religion: str | None = Field(default=None, max_length=100)
    religion_is_strict: bool = False
    preferred_caste: str | None = Field(default=None, max_length=100)
    preferred_city: str | None = Field(default=None, max_length=100)
    preferred_state: str | None = Field(default=None, max_length=100)
    preferred_mother_tongue: str | None = Field(default=None, max_length=50)
    preferred_annual_income: str | None = Field(default=None, max_length=100)

    @field_validator("age_max")
    @classmethod
    def validate_age_range(cls, v: int | None, info: Any) -> int | None:
        age_min = info.data.get("age_min")
        if v is not None and age_min is not None and v < age_min:
            raise ValueError("age_max must be >= age_min")
        return v

    @field_validator("preferred_height_max_cm")
    @classmethod
    def validate_height_range(cls, v: int | None, info: Any) -> int | None:
        h_min = info.data.get("preferred_height_min_cm")
        if v is not None and h_min is not None and v < h_min:
            raise ValueError("preferred_height_max_cm must be >= preferred_height_min_cm")
        return v


# ---------------------------------------------------------------------------
# Response schemas — Profile
# ---------------------------------------------------------------------------

class ProfileOut(BaseModel):
    """
    Full profile response — PRIVATE tier (profile owner / admin).

    Other tiers receive a subset of these fields; the service layer
    populates only the fields the viewer is allowed to see, setting
    everything else to None.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    platform_id: str
    managed_by: ProfileManagedByEnum

    # Identity
    first_name: str
    last_name: str | None = None  # None at PUBLIC tier
    gender: GenderEnum
    date_of_birth: date | None = None  # None at PUBLIC/REGISTERED (age only)
    age: int | None = None  # Computed from date_of_birth — always shown
    marital_status: MaritalStatusEnum | None = None  # None at PUBLIC

    # Physical
    height_cm: int | None = None

    # Professional
    education: str | None = None
    occupation: str | None = None
    annual_income: str | None = None  # PRIVATE tier only

    # Language
    mother_tongue: str | None = None
    languages_spoken: str | None = None

    # Location
    city: str | None = None
    state: str | None = None
    country: str | None = None
    pincode: str | None = None

    # Bio
    bio: str | None = None

    # Disability
    disability_type: DisabilityTypeEnum | None = None

    # Meta
    completeness_score: int = 0
    is_profile_visible: bool = True
    verification_status: VerificationStatusEnum = VerificationStatusEnum.PENDING

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # The viewer's resolved visibility tier for this profile
    visibility_tier: VisibilityTier | None = None

    # Photos
    photos: list[PhotoOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SensitiveDataOut(BaseModel):
    """
    Sensitive profile data response.

    Returned ONLY for the profile owner or via admin access.
    Contains decrypted plaintext — the API never returns ciphertext.
    """

    id: uuid.UUID
    profile_id: uuid.UUID

    # Disability
    disability_percentage: int | None = None
    disability_details: str | None = None
    disability_since: str | None = None
    mobility_aid: str | None = None

    # Health
    health_conditions: str | None = None

    # Religion/caste
    religion: str | None = None
    caste: str | None = None
    sub_caste: str | None = None

    # Family
    family_type: str | None = None
    family_status: str | None = None
    father_occupation: str | None = None
    mother_occupation: str | None = None
    siblings: str | None = None
    about_family: str | None = None

    # Contact
    contact_phone: str | None = None
    contact_email: str | None = None
    whatsapp_number: str | None = None

    model_config = {"from_attributes": True}


class PartnerPreferenceOut(BaseModel):
    """Partner preference response."""

    id: uuid.UUID
    profile_id: uuid.UUID

    preferred_gender: GenderEnum | None = None
    age_min: int | None = None
    age_max: int | None = None
    preferred_height_min_cm: int | None = None
    preferred_height_max_cm: int | None = None
    preferred_marital_statuses: list[MaritalStatusEnum] | None = None
    preferred_disability_types: list[DisabilityTypeEnum] | None = None
    preferred_education: str | None = None
    preferred_religion: str | None = None
    religion_is_strict: bool = False
    preferred_caste: str | None = None
    preferred_city: str | None = None
    preferred_state: str | None = None
    preferred_mother_tongue: str | None = None
    preferred_annual_income: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileWithSensitiveOut(BaseModel):
    """Combined profile + sensitive data response for the profile owner."""

    profile: ProfileOut
    sensitive_data: SensitiveDataOut | None = None
    partner_preferences: PartnerPreferenceOut | None = None
