"""
Tests for app.services.completeness_service — profile completeness scoring.

Validates:
  - Score calculation with all required fields only → 30 points
  - Score increases with optional fields
  - Score increases with sensitive data fields
  - Maximum score is 100
  - None/empty values don't contribute
  - Weights sum to exactly 100
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.models.enums import (
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
)
from app.services.completeness_service import (
    calculate_completeness,
    get_field_weights,
)


def _make_profile(**overrides) -> MagicMock:
    """Build a mock Profile with sensible defaults for testing."""
    defaults = {
        "first_name": "Rahul",
        "last_name": "Sharma",
        "gender": GenderEnum.MALE,
        "date_of_birth": date(1995, 6, 15),
        "marital_status": MaritalStatusEnum.NEVER_MARRIED,
        "managed_by": ProfileManagedByEnum.SELF,
        "height_cm": None,
        "education": None,
        "occupation": None,
        "annual_income": None,
        "mother_tongue": None,
        "languages_spoken": None,
        "city": None,
        "state": None,
        "country": "India",
        "pincode": None,
        "bio": None,
        "disability_type": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_sensitive(**overrides) -> MagicMock:
    """Build a mock SensitiveProfileData."""
    defaults = {
        "religion": None,
        "disability_percentage": None,
        "disability_since": None,
        "mobility_aid": None,
        "family_type": None,
        "family_status": None,
        "contact_phone": None,
        "whatsapp_number": None,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestCompletenessCalculation:

    def test_required_fields_only(self) -> None:
        """All 5 required fields filled → 30 points minimum.
        Plus country (1pt, default) + managed_by (4pt, default) = 35."""
        profile = _make_profile()
        score = calculate_completeness(profile)
        # 30 (required) + 1 (country default) + 4 (managed_by default) = 35
        assert score == 35

    def test_all_profile_fields_no_sensitive(self) -> None:
        """All profile fields filled, no sensitive data → 80 points max."""
        profile = _make_profile(
            height_cm=170,
            education="B.Tech",
            occupation="Software Engineer",
            annual_income="5-10 LPA",
            mother_tongue="Hindi",
            languages_spoken="Hindi, English",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            bio="Looking for a compatible partner.",
            disability_type="PHYSICAL",
        )
        score = calculate_completeness(profile, sensitive_data=None)
        assert score == 80  # 30 required + 50 optional

    def test_all_fields_maximum(self) -> None:
        """All profile + sensitive fields → 100 points."""
        profile = _make_profile(
            height_cm=170,
            education="B.Tech",
            occupation="Software Engineer",
            annual_income="5-10 LPA",
            mother_tongue="Hindi",
            languages_spoken="Hindi, English",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            bio="Looking for a compatible partner.",
            disability_type="PHYSICAL",
        )
        sensitive = _make_sensitive(
            religion="Hindu",
            disability_percentage=60,
            disability_since="Birth",
            mobility_aid="Wheelchair",
            family_type="Nuclear",
            family_status="Middle",
            contact_phone="encrypted_value_here",
            whatsapp_number="encrypted_value_here",
        )
        score = calculate_completeness(profile, sensitive)
        assert score == 100

    def test_none_fields_dont_count(self) -> None:
        """Explicitly None fields contribute nothing."""
        profile = _make_profile(
            first_name=None,  # required but explicitly None
        )
        score = calculate_completeness(profile)
        # Missing first_name = 30 - 6 = 24, plus country (1) + managed_by (4) = 29
        assert score == 29

    def test_empty_strings_dont_count(self) -> None:
        """Empty strings are treated as missing."""
        profile = _make_profile(bio="")
        score = calculate_completeness(profile)
        # bio is empty → same as required-only + defaults
        assert score == 35

    def test_weights_sum_to_100(self) -> None:
        """Field weights must always sum to exactly 100."""
        weights = get_field_weights()
        total = sum(weights.values())
        assert total == 100

    def test_sensitive_data_none(self) -> None:
        """When sensitive_data is None, only profile fields contribute."""
        profile = _make_profile()
        score_no_sensitive = calculate_completeness(profile, sensitive_data=None)
        score_with_empty = calculate_completeness(profile, sensitive_data=_make_sensitive())
        assert score_no_sensitive == score_with_empty

    def test_partial_sensitive_data(self) -> None:
        """Only filled sensitive fields contribute."""
        profile = _make_profile()
        sensitive = _make_sensitive(religion="Hindu", contact_phone="encrypted")
        score = calculate_completeness(profile, sensitive)
        # 35 (profile defaults) + 3 (religion) + 3 (contact_phone) = 41
        assert score == 41
