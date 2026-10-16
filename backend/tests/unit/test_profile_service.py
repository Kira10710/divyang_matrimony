"""Regression tests for profile-detail authorization."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import (
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
    VerificationStatusEnum,
    VisibilityTier,
)
from app.models.user import AdminRoleEnum
from app.services.profile_service import ProfileService


def _user(*, user_id=None, role=None, platform_id: str = "divyang_matrimony"):
    return SimpleNamespace(id=user_id or uuid4(), role=role, platform_id=platform_id)


def _profile(*, user_id=None, visible: bool = True, platform_id: str = "divyang_matrimony"):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id or uuid4(),
        platform_id=platform_id,
        managed_by=ProfileManagedByEnum.SELF,
        first_name="Priya",
        last_name="Patel",
        gender=GenderEnum.FEMALE,
        date_of_birth=date(1998, 3, 20),
        marital_status=MaritalStatusEnum.NEVER_MARRIED,
        height_cm=160,
        education="M.Sc.",
        occupation="Teacher",
        annual_income="3-5 LPA",
        mother_tongue="Gujarati",
        languages_spoken="Gujarati, Hindi",
        city="Ahmedabad",
        state="Gujarat",
        country="India",
        pincode="380001",
        bio="Profile bio",
        disability_type="PHYSICAL",
        completeness_score=75,
        is_profile_visible=visible,
        verification_status=VerificationStatusEnum.APPROVED,
        created_at=None,
        updated_at=None,
    )


@pytest.fixture
def profile_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def profile_service(profile_repo: AsyncMock) -> ProfileService:
    return ProfileService(profile_repo, AsyncMock(), AsyncMock())


class TestGetProfileByIdVisibility:
    async def test_hidden_profile_is_not_found_for_unrelated_registered_viewer(
        self, profile_service: ProfileService, profile_repo: AsyncMock
    ) -> None:
        target = _profile(visible=False)
        profile_repo.get_by_id.return_value = target

        with pytest.raises(NotFoundError, match="Profile not found"):
            await profile_service.get_profile_by_id(target.id, _user())

    async def test_hidden_profile_remains_available_to_its_owner(
        self, profile_service: ProfileService, profile_repo: AsyncMock
    ) -> None:
        owner = _user()
        target = _profile(user_id=owner.id, visible=False)
        profile_repo.get_by_id.return_value = target

        result = await profile_service.get_profile_by_id(target.id, owner)

        assert result.visibility_tier == VisibilityTier.PRIVATE
        assert result.user_id == owner.id

    async def test_hidden_profile_remains_available_to_admin(
        self, profile_service: ProfileService, profile_repo: AsyncMock
    ) -> None:
        target = _profile(visible=False)
        admin = _user(role=AdminRoleEnum.ADMIN)
        profile_repo.get_by_id.return_value = target

        result = await profile_service.get_profile_by_id(target.id, admin)

        assert result.visibility_tier == VisibilityTier.PRIVATE
        assert result.user_id == target.user_id

    async def test_hidden_profile_is_not_available_to_support(
        self, profile_service: ProfileService, profile_repo: AsyncMock
    ) -> None:
        target = _profile(visible=False)
        support = _user(role=AdminRoleEnum.SUPPORT)
        profile_repo.get_by_id.return_value = target

        with pytest.raises(NotFoundError, match="Profile not found"):
            await profile_service.get_profile_by_id(target.id, support)

    async def test_visible_profile_hides_internal_identifiers_from_registered_viewer(
        self, profile_service: ProfileService, profile_repo: AsyncMock
    ) -> None:
        target = _profile(visible=True)
        profile_repo.get_by_id.return_value = target

        result = await profile_service.get_profile_by_id(target.id, _user())

        assert result.visibility_tier == VisibilityTier.REGISTERED
        assert result.user_id is None
        assert result.platform_id is None
