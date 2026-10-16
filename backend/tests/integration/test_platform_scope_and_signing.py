"""Tenant isolation for admins (profile reads, photo moderation) and signed-URL failure handling.

Policy under test (Architecture §7.8): ADMIN/SUPPORT act only on their own
platform, taken from the authenticated user's DB row; only SUPER_ADMIN is global.
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends
from sqlalchemy import select

from app.core.dependencies import get_photo_repository, get_photo_service
from app.core.exceptions import ServiceUnavailableError
from app.core.security import create_access_token
from app.models.enums import GenderEnum, MaritalStatusEnum, ModerationStatusEnum
from app.models.profile import Profile
from app.models.profile_photo import ProfilePhoto
from app.models.user import AdminRoleEnum
from app.repositories.photo_repository import PhotoRepository
from app.schemas.photo import PhotoListOut
from app.services.photo_service import PhotoService

PLATFORM_A = "divyang_matrimony"
PLATFORM_B = "senior_matrimony"


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.platform_id)}"}


@pytest.fixture
def make_profile_with_photo(db_session_factory, make_user):
    """Create a user, a profile and a PENDING photo on the given platform."""

    async def _make(platform_id: str):
        user = await make_user(platform_id=platform_id)
        async with db_session_factory() as db:
            profile = Profile(
                user_id=user.id,
                platform_id=platform_id,
                first_name="Test",
                last_name="User",
                gender=GenderEnum.FEMALE,
                date_of_birth=date(1995, 1, 1),
                marital_status=MaritalStatusEnum.NEVER_MARRIED,
                country="India",
            )
            db.add(profile)
            await db.flush()
            photo = ProfilePhoto(
                profile_id=profile.id,
                storage_path=f"{platform_id}/o.jpg",
                medium_path=f"{platform_id}/m.jpg",
                thumbnail_path=f"{platform_id}/t.jpg",
                moderation_status=ModerationStatusEnum.PENDING,
            )
            db.add(photo)
            await db.commit()
            await db.refresh(profile)
            await db.refresh(photo)
            return user, profile, photo

    return lambda platform_id: asyncio.run(_make(platform_id))


def _photo_service_override(app_client, *, sign_ok: bool = True) -> None:
    blob = MagicMock()
    if sign_ok:
        blob.generate_signed_url.return_value = "https://signed.example/x"
    else:
        blob.generate_signed_url.side_effect = RuntimeError("kms down")
    bucket = MagicMock()
    bucket.blob.return_value = blob

    def _factory(repo: PhotoRepository = Depends(get_photo_repository)):  # noqa: B008
        return PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )

    app_client.app.dependency_overrides[get_photo_service] = _factory


def _photo_status(db_session_factory, photo_id) -> ModerationStatusEnum:
    async def _get():
        async with db_session_factory() as db:
            row = await db.execute(select(ProfilePhoto.moderation_status).where(ProfilePhoto.id == photo_id))
            return row.scalar_one()

    return asyncio.run(_get())


# ---------------------------------------------------------------------------
# Profile reads
# ---------------------------------------------------------------------------


def test_admin_profile_read_is_limited_to_own_platform(app_client, make_admin, make_profile_with_photo) -> None:
    _, profile_b, _ = make_profile_with_photo(PLATFORM_B)
    admin_a = asyncio.run(make_admin(platform_id=PLATFORM_A))
    admin_b = asyncio.run(make_admin(platform_id=PLATFORM_B))
    super_a = asyncio.run(make_admin(platform_id=PLATFORM_A, role=AdminRoleEnum.SUPER_ADMIN))
    support_a = asyncio.run(make_admin(platform_id=PLATFORM_A, role=AdminRoleEnum.SUPPORT))
    photo_svc = AsyncMock()
    photo_svc.list_photos.return_value = PhotoListOut(photos=[], total=0)
    app_client.app.dependency_overrides[get_photo_service] = lambda: photo_svc
    url = f"/api/v1/profiles/{profile_b.id}"

    try:
        assert app_client.get(url, headers=_headers(admin_b)).status_code == 200
        assert app_client.get(url, headers=_headers(admin_a)).status_code == 404
        assert app_client.get(url, headers=_headers(support_a)).status_code == 404
        assert app_client.get(url, headers=_headers(super_a)).status_code == 200
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


# ---------------------------------------------------------------------------
# Photo moderation
# ---------------------------------------------------------------------------


def test_moderation_queue_is_scoped_to_admin_platform(app_client, make_admin, make_profile_with_photo) -> None:
    _, _, photo_a = make_profile_with_photo(PLATFORM_A)
    _, _, photo_b = make_profile_with_photo(PLATFORM_B)
    admin_a = asyncio.run(make_admin(platform_id=PLATFORM_A))
    super_b = asyncio.run(make_admin(platform_id=PLATFORM_B, role=AdminRoleEnum.SUPER_ADMIN))
    _photo_service_override(app_client)
    url = "/api/admin/photos/moderation-queue"

    try:
        ids_a = {p["id"] for p in app_client.get(url, headers=_headers(admin_a)).json()["data"]["photos"]}
        assert str(photo_a.id) in ids_a
        assert str(photo_b.id) not in ids_a

        ids_super = {p["id"] for p in app_client.get(url, headers=_headers(super_b)).json()["data"]["photos"]}
        assert {str(photo_a.id), str(photo_b.id)} <= ids_super
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_cross_platform_admin_cannot_approve_or_reject(
    app_client, make_admin, make_profile_with_photo, db_session_factory
) -> None:
    _, _, photo_b = make_profile_with_photo(PLATFORM_B)
    admin_a = asyncio.run(make_admin(platform_id=PLATFORM_A))
    _photo_service_override(app_client)

    try:
        approve = app_client.put(f"/api/admin/photos/{photo_b.id}/approve", headers=_headers(admin_a))
        reject = app_client.put(
            f"/api/admin/photos/{photo_b.id}/reject",
            headers=_headers(admin_a),
            json={"rejection_reason": "not allowed"},
        )
        assert approve.status_code == 404
        assert reject.status_code == 404
        assert _photo_status(db_session_factory, photo_b.id) == ModerationStatusEnum.PENDING
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_same_platform_admin_and_super_admin_can_moderate(
    app_client, make_admin, make_profile_with_photo, db_session_factory
) -> None:
    _, _, photo_one = make_profile_with_photo(PLATFORM_B)
    _, _, photo_two = make_profile_with_photo(PLATFORM_B)
    admin_b = asyncio.run(make_admin(platform_id=PLATFORM_B))
    super_a = asyncio.run(make_admin(platform_id=PLATFORM_A, role=AdminRoleEnum.SUPER_ADMIN))
    _photo_service_override(app_client)

    try:
        ok = app_client.put(f"/api/admin/photos/{photo_one.id}/approve", headers=_headers(admin_b))
        assert ok.status_code == 200
        assert _photo_status(db_session_factory, photo_one.id) == ModerationStatusEnum.APPROVED

        cross = app_client.put(
            f"/api/admin/photos/{photo_two.id}/reject",
            headers=_headers(super_a),
            json={"rejection_reason": "blurry"},
        )
        assert cross.status_code == 200
        assert _photo_status(db_session_factory, photo_two.id) == ModerationStatusEnum.REJECTED
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


# ---------------------------------------------------------------------------
# Signed URL generation
# ---------------------------------------------------------------------------


def _service(blob: MagicMock) -> PhotoService:
    bucket = MagicMock()
    bucket.blob.return_value = blob
    return PhotoService(
        photo_repo=MagicMock(),
        bucket_factory=lambda: bucket,
        gcs_credentials_factory=lambda: MagicMock(),
    )


def test_signed_url_returns_the_signed_url_on_success() -> None:
    from datetime import timedelta

    blob = MagicMock()
    blob.generate_signed_url.return_value = "https://signed.example/ok"
    assert _service(blob)._signed_url("a/b.jpg", timedelta(minutes=5)) == "https://signed.example/ok"


def test_signed_url_failure_raises_service_unavailable_not_empty_string() -> None:
    from datetime import timedelta

    blob = MagicMock()
    blob.generate_signed_url.side_effect = RuntimeError("signing failed")
    with pytest.raises(ServiceUnavailableError):
        _service(blob)._signed_url("a/b.jpg", timedelta(minutes=5))


def test_signing_failure_returns_503_with_standard_error_envelope(
    app_client, make_admin, make_profile_with_photo
) -> None:
    make_profile_with_photo(PLATFORM_A)
    admin_a = asyncio.run(make_admin(platform_id=PLATFORM_A))
    _photo_service_override(app_client, sign_ok=False)

    try:
        response = app_client.get("/api/admin/photos/moderation-queue", headers=_headers(admin_a))
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["errors"]
    assert "kms down" not in response.text  # internal error detail is not leaked
