"""Phase B hardening: server-resolved platform, photo authorization, metadata stripping,
SUPPORT moderation denial, primary-photo consistency and admin provisioning."""

from __future__ import annotations

import asyncio
import io
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import Depends
from PIL import Image
from sqlalchemy import delete, select

from app.core.dependencies import get_photo_repository, get_photo_service
from app.core.exceptions import BadRequestError, ConflictError
from app.core.security import create_access_token, verify_password
from app.models.enums import GenderEnum, MaritalStatusEnum, ModerationStatusEnum
from app.models.platform_config import PlatformConfig
from app.models.profile import Profile
from app.models.profile_photo import ProfilePhoto
from app.models.user import AdminRoleEnum, User
from app.repositories.photo_repository import PhotoRepository
from app.services.admin_service import provision_admin
from app.services.photo_service import PhotoService

PLATFORM = "divyang_matrimony"
OTHER = "senior_matrimony"


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.platform_id)}"}


def _jpeg(*, exif: bool = False, size=(16, 8)) -> bytes:
    img = Image.new("RGB", size, (10, 120, 200))
    out = io.BytesIO()
    if exif:
        data = Image.Exif()
        data[0x010F] = "SecretCameraMaker"
        data[0x0112] = 6  # rotate 90 degrees
        gps = data.get_ifd(0x8825)
        gps[1] = "N"
        gps[2] = (12.0, 34.0, 56.0)
        img.save(out, "JPEG", exif=data)
    else:
        img.save(out, "JPEG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Server-resolved platform on auth routes
# ---------------------------------------------------------------------------


class TestPlatformIsServerResolved:
    def test_send_otp_without_platform_uses_server_platform(self, app_client) -> None:
        assert app_client.post("/api/v1/auth/send-otp", json={"phone": "9876543210"}).status_code == 200

    def test_send_otp_with_matching_platform_is_accepted(self, app_client) -> None:
        body = {"phone": "9876543210", "platform_id": PLATFORM}
        assert app_client.post("/api/v1/auth/send-otp", json=body).status_code == 200

    def test_send_otp_with_foreign_platform_is_rejected(self, app_client) -> None:
        body = {"phone": "9876543210", "platform_id": OTHER}
        response = app_client.post("/api/v1/auth/send-otp", json=body)
        assert response.status_code == 400
        assert response.json()["success"] is False

    def test_verify_otp_with_foreign_platform_is_rejected(self, app_client) -> None:
        body = {"phone": "9876543210", "otp": "000000", "platform_id": OTHER}
        assert app_client.post("/api/v1/auth/verify-otp", json=body).status_code == 400

    def test_admin_login_with_foreign_platform_is_rejected(self, app_client, make_admin) -> None:
        admin = asyncio.run(make_admin(password="CorrectHorse123"))
        body = {"email": admin.email, "password": "CorrectHorse123", "platform_id": OTHER}
        assert app_client.post("/api/v1/auth/login-admin", json=body).status_code == 400


# ---------------------------------------------------------------------------
# Fixtures for photo tests
# ---------------------------------------------------------------------------


@pytest.fixture
def make_profile(db_session_factory, make_user):
    async def _make(platform_id: str = PLATFORM):
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
            await db.commit()
            await db.refresh(profile)
            return user, profile

    return lambda platform_id=PLATFORM: asyncio.run(_make(platform_id))


@pytest.fixture
def add_photo(db_session_factory):
    async def _add(profile_id, *, status=ModerationStatusEnum.APPROVED, primary=False, order=0):
        async with db_session_factory() as db:
            photo = ProfilePhoto(
                profile_id=profile_id,
                storage_path=f"profiles/{profile_id}/{order}_o.jpg",
                medium_path=f"profiles/{profile_id}/{order}_m.jpg",
                thumbnail_path=f"profiles/{profile_id}/{order}_t.jpg",
                moderation_status=status,
                is_primary=primary,
                display_order=order,
            )
            db.add(photo)
            await db.commit()
            await db.refresh(photo)
            return photo

    return lambda profile_id, **kw: asyncio.run(_add(profile_id, **kw))


@pytest.fixture
def photo_state(db_session_factory):
    async def _get(photo_id):
        async with db_session_factory() as db:
            row = await db.execute(
                select(ProfilePhoto.moderation_status, ProfilePhoto.is_primary).where(ProfilePhoto.id == photo_id)
            )
            return row.one_or_none()

    return lambda photo_id: asyncio.run(_get(photo_id))


def _override_photo_service(app_client, bucket) -> None:
    def _factory(repo: PhotoRepository = Depends(get_photo_repository)):  # noqa: B008
        return PhotoService(photo_repo=repo, bucket_factory=lambda: bucket, gcs_credentials_factory=lambda: MagicMock())

    app_client.app.dependency_overrides[get_photo_service] = _factory


def _simple_bucket() -> MagicMock:
    blob = MagicMock()
    blob.generate_signed_url.return_value = "https://signed.example/x"
    blob.exists.return_value = True
    blob.size = 1000
    blob.download_as_bytes.return_value = _jpeg()
    bucket = MagicMock()
    bucket.blob.return_value = blob
    return bucket


# ---------------------------------------------------------------------------
# Own-photo authorization (upload, list, delete, primary)
# ---------------------------------------------------------------------------


class TestPhotoOwnership:
    def test_requests_without_a_profile_are_404(self, app_client, make_user) -> None:
        user = asyncio.run(make_user())
        _override_photo_service(app_client, _simple_bucket())
        try:
            upload = app_client.post("/api/v1/profiles/me/photos/upload-sessions", headers=_headers(user))
            listing = app_client.get("/api/v1/profiles/me/photos", headers=_headers(user))
            assert (upload.status_code, listing.status_code) == (404, 404)
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)

    def test_anonymous_requests_are_rejected(self, app_client) -> None:
        assert app_client.get("/api/v1/profiles/me/photos").status_code in (401, 403)
        assert app_client.post("/api/v1/profiles/me/photos/upload-sessions").status_code in (401, 403)

    def test_other_users_cannot_delete_or_promote_a_photo(
        self, app_client, make_profile, add_photo, photo_state
    ) -> None:
        owner, owner_profile = make_profile()
        attacker, _ = make_profile()
        photo = add_photo(owner_profile.id, primary=False)
        _override_photo_service(app_client, _simple_bucket())
        try:
            delete = app_client.delete(f"/api/v1/profiles/me/photos/{photo.id}", headers=_headers(attacker))
            primary = app_client.patch(f"/api/v1/profiles/me/photos/{photo.id}/primary", headers=_headers(attacker))
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)

        assert delete.status_code == 404
        assert primary.status_code == 404
        state = photo_state(photo.id)
        assert state is not None and state.is_primary is False

    def test_registering_another_profiles_object_paths_is_rejected(self, app_client, make_profile) -> None:
        _, victim_profile = make_profile()
        attacker, _ = make_profile()
        base = f"profiles/{victim_profile.id}/x"
        _override_photo_service(app_client, _simple_bucket())
        try:
            response = app_client.post(
                "/api/v1/profiles/me/photos",
                headers=_headers(attacker),
                json={
                    "storage_path": f"{base}_original.jpg",
                    "medium_path": f"{base}_medium.jpg",
                    "thumbnail_path": f"{base}_thumbnail.jpg",
                },
            )
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)
        assert response.status_code == 400

    def test_primary_photo_must_be_approved(self, app_client, make_profile, add_photo, photo_state) -> None:
        owner, profile = make_profile()
        pending = add_photo(profile.id, status=ModerationStatusEnum.PENDING)
        _override_photo_service(app_client, _simple_bucket())
        try:
            response = app_client.patch(f"/api/v1/profiles/me/photos/{pending.id}/primary", headers=_headers(owner))
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)
        assert response.status_code == 400
        assert photo_state(pending.id).is_primary is False

    def test_deleting_the_primary_promotes_the_next_approved_photo(
        self, app_client, make_profile, add_photo, photo_state
    ) -> None:
        owner, profile = make_profile()
        primary = add_photo(profile.id, primary=True, order=0)
        runner_up = add_photo(profile.id, order=1)
        _override_photo_service(app_client, _simple_bucket())
        try:
            response = app_client.delete(f"/api/v1/profiles/me/photos/{primary.id}", headers=_headers(owner))
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)
        assert response.status_code == 200
        assert photo_state(runner_up.id).is_primary is True


# ---------------------------------------------------------------------------
# Moderation: SUPPORT denied, rejected primary replaced
# ---------------------------------------------------------------------------


class TestModerationRoles:
    def test_support_cannot_view_approve_or_reject(
        self, app_client, make_admin, make_profile, add_photo, photo_state
    ) -> None:
        _, profile = make_profile()
        photo = add_photo(profile.id, status=ModerationStatusEnum.PENDING)
        support = asyncio.run(make_admin(role=AdminRoleEnum.SUPPORT))
        _override_photo_service(app_client, _simple_bucket())
        try:
            queue = app_client.get("/api/admin/photos/moderation-queue", headers=_headers(support))
            approve = app_client.put(f"/api/admin/photos/{photo.id}/approve", headers=_headers(support))
            reject = app_client.put(
                f"/api/admin/photos/{photo.id}/reject", headers=_headers(support), json={"rejection_reason": "no"}
            )
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)
        assert (queue.status_code, approve.status_code, reject.status_code) == (403, 403, 403)
        assert photo_state(photo.id).moderation_status == ModerationStatusEnum.PENDING

    def test_rejecting_the_primary_clears_it_and_promotes_another(
        self, app_client, make_admin, make_profile, add_photo, photo_state
    ) -> None:
        _, profile = make_profile()
        primary = add_photo(profile.id, primary=True, order=0)
        runner_up = add_photo(profile.id, order=1)
        admin = asyncio.run(make_admin())
        _override_photo_service(app_client, _simple_bucket())
        try:
            response = app_client.put(
                f"/api/admin/photos/{primary.id}/reject",
                headers=_headers(admin),
                json={"rejection_reason": "not a face photo"},
            )
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)
        assert response.status_code == 200
        rejected = photo_state(primary.id)
        assert rejected.moderation_status == ModerationStatusEnum.REJECTED and rejected.is_primary is False
        assert photo_state(runner_up.id).is_primary is True


# ---------------------------------------------------------------------------
# Metadata stripping
# ---------------------------------------------------------------------------


class TestMetadataStripping:
    def test_exif_gps_and_orientation_are_removed_and_pixels_rotated(self) -> None:
        raw = _jpeg(exif=True, size=(16, 8))
        assert len(Image.open(io.BytesIO(raw)).getexif()) > 0

        clean, content_type = PhotoService._strip_metadata(raw, "profiles/x/o.jpg")

        cleaned = Image.open(io.BytesIO(clean))
        assert len(cleaned.getexif()) == 0
        assert not cleaned.getexif().get_ifd(0x8825)
        assert content_type == "image/jpeg"
        assert cleaned.size == (8, 16)  # orientation 6 applied to the pixels

    @pytest.mark.parametrize(("fmt", "content_type"), [("PNG", "image/png"), ("WEBP", "image/webp")])
    def test_other_formats_are_reencoded(self, fmt: str, content_type: str) -> None:
        out = io.BytesIO()
        Image.new("RGB", (8, 8)).save(out, fmt)
        clean, ctype = PhotoService._strip_metadata(out.getvalue(), "p")
        assert ctype == content_type
        assert Image.open(io.BytesIO(clean)).format == fmt

    def test_corrupt_images_are_rejected(self) -> None:
        with pytest.raises(BadRequestError):
            PhotoService._strip_metadata(b"\xff\xd8\xff\xe0" + b"\x00" * 28, "p")

    def test_oversized_pixel_counts_are_rejected_before_decoding(self, monkeypatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "PHOTO_MAX_PIXELS", 10)
        with pytest.raises(BadRequestError, match="too many pixels"):
            PhotoService._strip_metadata(_jpeg(size=(16, 16)), "p")

    def test_registration_uploads_the_cleaned_bytes(self, app_client, make_profile) -> None:
        user, profile = make_profile()
        blob = MagicMock()
        blob.exists.return_value = True
        blob.size = 5000
        blob.download_as_bytes.return_value = _jpeg(exif=True)
        blob.generate_signed_url.return_value = "https://signed.example/x"
        bucket = MagicMock()
        bucket.blob.return_value = blob
        base = f"profiles/{profile.id}/abc"
        _override_photo_service(app_client, bucket)
        try:
            response = app_client.post(
                "/api/v1/profiles/me/photos",
                headers=_headers(user),
                json={
                    "storage_path": f"{base}_original.jpg",
                    "medium_path": f"{base}_medium.jpg",
                    "thumbnail_path": f"{base}_thumbnail.jpg",
                },
            )
        finally:
            app_client.app.dependency_overrides.pop(get_photo_service, None)

        assert response.status_code == 201, response.json()
        assert blob.upload_from_string.call_count == 3
        uploaded = blob.upload_from_string.call_args.args[0]
        assert len(Image.open(io.BytesIO(uploaded)).getexif()) == 0


# ---------------------------------------------------------------------------
# Admin provisioning
# ---------------------------------------------------------------------------


@pytest.fixture
def platform_config(db_session_factory):
    """Seed platform_config rows. The shared conftest does not truncate this table,
    so each row is removed again after the test (and any stale one before it)."""
    created: list[str] = []

    async def _delete(keys: list[str]):
        async with db_session_factory() as db:
            await db.execute(delete(PlatformConfig).where(PlatformConfig.platform_key.in_(keys)))
            await db.commit()

    async def _make(key: str, *, active: bool = True):
        await _delete([key])
        created.append(key)
        async with db_session_factory() as db:
            db.add(
                PlatformConfig(
                    platform_key=key,
                    app_name=key,
                    is_active=active,
                    settings={"minimum_age": 18, "maximum_age": 80, "require_disability": True},
                )
            )
            await db.commit()

    yield lambda key, **kw: asyncio.run(_make(key, **kw))
    if created:
        asyncio.run(_delete(created))


def _provision(db_session_factory, **kwargs) -> User:
    async def _run():
        async with db_session_factory() as db:
            admin = await provision_admin(db, **kwargs)
            await db.commit()
            return admin

    return asyncio.run(_run())


GOOD = {"email": "Ops@Example.com", "password": "Sturdy-pass-2026", "role": "ADMIN", "platform_id": PLATFORM}


class TestAdminProvisioning:
    def test_creates_a_platform_scoped_admin_with_hashed_password(self, db_session_factory, platform_config) -> None:
        platform_config(PLATFORM)
        admin = _provision(db_session_factory, **GOOD)
        assert admin.role == AdminRoleEnum.ADMIN
        assert admin.platform_id == PLATFORM
        assert admin.email == "ops@example.com"
        assert admin.password_hash != GOOD["password"]
        assert verify_password(GOOD["password"], admin.password_hash)

    def test_platform_is_required_never_defaulted(self, db_session_factory, platform_config) -> None:
        platform_config(PLATFORM)
        for missing in (None, "", "   "):
            with pytest.raises(BadRequestError, match="platform"):
                _provision(db_session_factory, **{**GOOD, "platform_id": missing})

    def test_unknown_or_inactive_platform_is_rejected(self, db_session_factory, platform_config) -> None:
        platform_config(OTHER, active=False)
        for key in ("no_such_platform", OTHER):
            with pytest.raises(BadRequestError, match="does not exist or is not active"):
                _provision(db_session_factory, **{**GOOD, "platform_id": key})

    def test_super_admin_needs_explicit_authorization(self, db_session_factory, platform_config) -> None:
        platform_config(PLATFORM)
        with pytest.raises(BadRequestError, match="SUPER_ADMIN"):
            _provision(db_session_factory, **{**GOOD, "role": "SUPER_ADMIN"})
        admin = _provision(db_session_factory, **{**GOOD, "role": "SUPER_ADMIN", "allow_super_admin": True})
        assert admin.role == AdminRoleEnum.SUPER_ADMIN

    @pytest.mark.parametrize("role", ["owner", "", None])
    def test_unknown_role_is_rejected(self, db_session_factory, platform_config, role) -> None:
        platform_config(PLATFORM)
        with pytest.raises(BadRequestError, match="role"):
            _provision(db_session_factory, **{**GOOD, "role": role})

    @pytest.mark.parametrize("password", ["short1", "alllettersnodigits", "1234567890123"])
    def test_weak_passwords_are_rejected(self, db_session_factory, platform_config, password) -> None:
        platform_config(PLATFORM)
        with pytest.raises(BadRequestError, match="password"):
            _provision(db_session_factory, **{**GOOD, "password": password})

    def test_invalid_email_and_duplicates_are_rejected(self, db_session_factory, platform_config) -> None:
        platform_config(PLATFORM)
        with pytest.raises(BadRequestError, match="email"):
            _provision(db_session_factory, **{**GOOD, "email": "not-an-email"})
        _provision(db_session_factory, **GOOD)
        with pytest.raises(ConflictError):
            _provision(db_session_factory, **{**GOOD, "email": "ops@example.com"})

    def test_secrets_are_not_logged(self, db_session_factory, platform_config) -> None:
        import structlog

        platform_config(PLATFORM)
        with structlog.testing.capture_logs() as logs:
            _provision(db_session_factory, **GOOD)
        text = repr(logs)
        assert GOOD["password"] not in text
        assert "argon2" not in text
        assert "example.com" not in text
