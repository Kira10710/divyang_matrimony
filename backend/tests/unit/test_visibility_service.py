"""
Tests for app.services.visibility_service — tier resolution + field filtering.

Validates:
  - Owner gets PRIVATE tier
  - Admin gets PRIVATE tier
  - Regular user gets REGISTERED
  - Subscriber gets SUBSCRIBERS
  - Mutual interest gets MATCHED
  - Field filtering at each tier
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from app.models.enums import (
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
    VerificationStatusEnum,
    VisibilityTier,
)
from app.models.user import AdminRoleEnum
from app.services.visibility_service import (
    filter_profile_for_tier,
    get_allowed_profile_fields,
    get_allowed_sensitive_fields,
    resolve_visibility_tier,
)


def _make_user(user_id=None, role=None) -> MagicMock:
    mock = MagicMock()
    mock.id = user_id or uuid4()
    mock.role = role
    return mock


def _make_profile(user_id=None, profile_id=None) -> MagicMock:
    mock = MagicMock()
    mock.id = profile_id or uuid4()
    mock.user_id = user_id or uuid4()
    mock.platform_id = "divyang_matrimony"
    mock.first_name = "Priya"
    mock.last_name = "Patel"
    mock.gender = GenderEnum.FEMALE
    mock.date_of_birth = date(1998, 3, 20)
    mock.marital_status = MaritalStatusEnum.NEVER_MARRIED
    mock.managed_by = ProfileManagedByEnum.PARENT
    mock.height_cm = 160
    mock.education = "M.Sc."
    mock.occupation = "Teacher"
    mock.annual_income = "3-5 LPA"
    mock.mother_tongue = "Gujarati"
    mock.languages_spoken = "Gujarati, Hindi, English"
    mock.city = "Ahmedabad"
    mock.state = "Gujarat"
    mock.country = "India"
    mock.pincode = "380001"
    mock.bio = "Family is managing this profile."
    mock.disability_type = "PHYSICAL"
    mock.completeness_score = 75
    mock.is_profile_visible = True
    mock.verification_status = VerificationStatusEnum.APPROVED
    mock.created_at = None
    mock.updated_at = None
    return mock


class TestResolveTier:

    def test_owner_gets_private(self) -> None:
        user_id = uuid4()
        viewer = _make_user(user_id=user_id)
        profile = _make_profile(user_id=user_id)
        tier = resolve_visibility_tier(viewer, profile)
        assert tier == VisibilityTier.PRIVATE

    def test_admin_gets_private(self) -> None:
        viewer = _make_user(role=AdminRoleEnum.ADMIN)
        profile = _make_profile()
        tier = resolve_visibility_tier(viewer, profile)
        assert tier == VisibilityTier.PRIVATE

    def test_super_admin_gets_private(self) -> None:
        viewer = _make_user(role=AdminRoleEnum.SUPER_ADMIN)
        profile = _make_profile()
        tier = resolve_visibility_tier(viewer, profile)
        assert tier == VisibilityTier.PRIVATE

    def test_support_gets_registered(self) -> None:
        """SUPPORT role is NOT admin-level for visibility."""
        viewer = _make_user(role=AdminRoleEnum.SUPPORT)
        profile = _make_profile()
        tier = resolve_visibility_tier(viewer, profile)
        assert tier == VisibilityTier.REGISTERED

    def test_regular_user_gets_registered(self) -> None:
        viewer = _make_user()
        profile = _make_profile()
        tier = resolve_visibility_tier(viewer, profile)
        assert tier == VisibilityTier.REGISTERED

    def test_subscriber_gets_subscribers(self) -> None:
        viewer = _make_user()
        profile = _make_profile()
        tier = resolve_visibility_tier(
            viewer, profile, has_active_subscription=True
        )
        assert tier == VisibilityTier.SUBSCRIBERS

    def test_mutual_interest_gets_matched(self) -> None:
        viewer = _make_user()
        profile = _make_profile()
        tier = resolve_visibility_tier(
            viewer, profile, has_mutual_interest=True
        )
        assert tier == VisibilityTier.MATCHED

    def test_mutual_interest_trumps_subscription(self) -> None:
        """Matched > Subscribers."""
        viewer = _make_user()
        profile = _make_profile()
        tier = resolve_visibility_tier(
            viewer, profile,
            has_active_subscription=True,
            has_mutual_interest=True,
        )
        assert tier == VisibilityTier.MATCHED


class TestAllowedFields:

    def test_public_has_first_name(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.PUBLIC)
        assert "first_name" in fields

    def test_public_does_not_have_last_name(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.PUBLIC)
        assert "last_name" not in fields

    def test_registered_has_last_name(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.REGISTERED)
        assert "last_name" in fields

    def test_registered_does_not_have_annual_income(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.REGISTERED)
        assert "annual_income" not in fields

    def test_private_has_annual_income(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.PRIVATE)
        assert "annual_income" in fields

    def test_private_has_date_of_birth(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.PRIVATE)
        assert "date_of_birth" in fields

    def test_registered_does_not_have_date_of_birth(self) -> None:
        fields = get_allowed_profile_fields(VisibilityTier.REGISTERED)
        assert "date_of_birth" not in fields


class TestAllowedSensitiveFields:

    def test_public_sees_nothing(self) -> None:
        assert get_allowed_sensitive_fields(VisibilityTier.PUBLIC) == set()

    def test_registered_sees_nothing(self) -> None:
        assert get_allowed_sensitive_fields(VisibilityTier.REGISTERED) == set()

    def test_subscribers_see_religion(self) -> None:
        fields = get_allowed_sensitive_fields(VisibilityTier.SUBSCRIBERS)
        assert "religion" in fields
        assert "caste" in fields
        assert "disability_percentage" in fields

    def test_subscribers_dont_see_contact(self) -> None:
        fields = get_allowed_sensitive_fields(VisibilityTier.SUBSCRIBERS)
        assert "contact_phone" not in fields
        assert "whatsapp_number" not in fields

    def test_matched_sees_contact(self) -> None:
        fields = get_allowed_sensitive_fields(VisibilityTier.MATCHED)
        assert "contact_phone" in fields
        assert "whatsapp_number" in fields
        assert "disability_details" in fields

    def test_private_sees_everything(self) -> None:
        fields = get_allowed_sensitive_fields(VisibilityTier.PRIVATE)
        assert "contact_phone" in fields
        assert "religion" in fields
        assert "about_family" in fields


class TestFilterProfileForTier:

    def test_public_tier_nulls_last_name(self) -> None:
        profile = _make_profile()
        out = filter_profile_for_tier(profile, VisibilityTier.PUBLIC)
        assert out.first_name == "Priya"
        assert out.last_name is None
        assert out.age is not None  # age always shown

    def test_registered_shows_last_name(self) -> None:
        profile = _make_profile()
        out = filter_profile_for_tier(profile, VisibilityTier.REGISTERED)
        assert out.last_name == "Patel"
        assert out.annual_income is None  # PRIVATE only

    def test_private_shows_everything(self) -> None:
        profile = _make_profile()
        out = filter_profile_for_tier(profile, VisibilityTier.PRIVATE)
        assert out.last_name == "Patel"
        assert out.annual_income == "3-5 LPA"
        assert out.date_of_birth == date(1998, 3, 20)

    def test_age_always_computed(self) -> None:
        profile = _make_profile()
        for tier in VisibilityTier:
            out = filter_profile_for_tier(profile, tier)
            assert out.age is not None
            assert out.age > 0

    def test_visibility_tier_included(self) -> None:
        profile = _make_profile()
        out = filter_profile_for_tier(profile, VisibilityTier.SUBSCRIBERS)
        assert out.visibility_tier == VisibilityTier.SUBSCRIBERS
