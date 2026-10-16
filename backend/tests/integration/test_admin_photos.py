"""
Integration tests for Admin Photo Moderation (Phase 4.3).

Ensures that only admins can access moderation queue, approve, and reject photos.
"""
import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.dependencies import get_photo_repository, get_photo_service
from app.core.security import create_access_token
from app.models.enums import GenderEnum, MaritalStatusEnum, ModerationStatusEnum
from app.models.profile import Profile
from app.models.profile_photo import ProfilePhoto
from app.models.user import AdminRoleEnum
from app.repositories.photo_repository import PhotoRepository
from app.services.photo_service import PhotoService


@pytest.fixture
def admin_auth_headers(make_admin) -> dict:
    admin = asyncio.run(make_admin())
    token = create_access_token(
        str(admin.id),
        str(admin.platform_id),
        role=admin.role.value if hasattr(admin, "role") else AdminRoleEnum.ADMIN.value
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def user_auth_headers(make_user) -> dict:
    user = asyncio.run(make_user())
    token = create_access_token(str(user.id), str(user.platform_id))
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def pending_photo(db_session_factory, make_user) -> ProfilePhoto:
    async def _create():
        user = await make_user()
        profile = Profile(
            user_id=user.id,
            first_name="Test",
            last_name="User",
            gender=GenderEnum.MALE,
            date_of_birth=date(1995, 1, 1),
            marital_status=MaritalStatusEnum.NEVER_MARRIED,
            country="India",
        )
        async with db_session_factory() as db:
            db.add(profile)
            await db.flush()
            photo = ProfilePhoto(
                profile_id=profile.id,
                storage_path="test/original.jpg",
                medium_path="test/medium.jpg",
                thumbnail_path="test/thumbnail.jpg",
                moderation_status=ModerationStatusEnum.PENDING,
            )
            db.add(photo)
            await db.commit()
            await db.refresh(photo)
            return photo

    return asyncio.run(_create())


@pytest.fixture
def mock_photo_service():
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed.example/x"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    def _factory(repo: PhotoRepository = Depends(get_photo_repository)):  # noqa: B008 - FastAPI dependency injection
        return PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )

    return _factory


def test_admin_get_moderation_queue(
    app_client: TestClient,
    admin_auth_headers: dict,
    pending_photo: ProfilePhoto,
    mock_photo_service: PhotoService,
):
    app_client.app.dependency_overrides[get_photo_service] = mock_photo_service
    """Admin can get pending photos."""
    try:
        response = app_client.get(
            "/api/admin/photos/moderation-queue",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["photos"]) >= 1

        photo_data = next((p for p in data["data"]["photos"] if p["id"] == str(pending_photo.id)), None)
        assert photo_data is not None
        assert photo_data["moderation_status"] == "PENDING"
        assert "signed_urls" in photo_data
        assert photo_data["signed_urls"]["thumbnail_url"] != ""
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_user_cannot_access_moderation_queue(
    app_client: TestClient,
    user_auth_headers: dict,
    mock_photo_service: PhotoService,
):
    app_client.app.dependency_overrides[get_photo_service] = mock_photo_service
    """Regular users get 403 when accessing admin routes."""
    try:
        response = app_client.get(
            "/api/admin/photos/moderation-queue",
            headers=user_auth_headers,
        )
        assert response.status_code == 403
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_admin_approve_photo(
    app_client: TestClient,
    admin_auth_headers: dict,
    pending_photo: ProfilePhoto,
    db_session_factory,
    mock_photo_service: PhotoService,
):
    app_client.app.dependency_overrides[get_photo_service] = mock_photo_service
    """Admin can approve a photo."""
    try:
        response = app_client.put(
            f"/api/admin/photos/{pending_photo.id}/approve",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["moderation_status"] == "APPROVED"

        async def _verify():
            async with db_session_factory() as db:
                photo = await db.get(ProfilePhoto, pending_photo.id)
                assert photo.moderation_status == ModerationStatusEnum.APPROVED
        asyncio.run(_verify())
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_admin_reject_photo(
    app_client: TestClient,
    admin_auth_headers: dict,
    pending_photo: ProfilePhoto,
    db_session_factory,
    mock_photo_service: PhotoService,
):
    app_client.app.dependency_overrides[get_photo_service] = mock_photo_service
    """Admin can reject a photo with a reason."""
    try:
        reason = "Inappropriate content"
        response = app_client.put(
            f"/api/admin/photos/{pending_photo.id}/reject",
            headers=admin_auth_headers,
            json={"rejection_reason": reason},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["moderation_status"] == "REJECTED"
        assert data["data"]["rejection_reason"] == reason

        async def _verify():
            async with db_session_factory() as db:
                photo = await db.get(ProfilePhoto, pending_photo.id)
                assert photo.moderation_status == ModerationStatusEnum.REJECTED
                assert photo.rejection_reason == reason
        asyncio.run(_verify())
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)
