"""
Unit tests for PhotoService.

Firebase's bucket is mocked throughout — these tests exercise only the
service logic: tier-gated URL generation, 6-photo limit enforcement,
moderation-status gating, ownership checks, and the delete/primary flows.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import ModerationStatusEnum, VisibilityTier
from app.models.profile_photo import ProfilePhoto
from app.repositories.photo_repository import MAX_PHOTOS_PER_PROFILE
from app.schemas.photo import PhotoRegisterRequest
from app.services.photo_service import PhotoService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_photo(
    *,
    profile_id: uuid.UUID | None = None,
    moderation_status: ModerationStatusEnum = ModerationStatusEnum.APPROVED,
    is_primary: bool = False,
    display_order: int = 0,
) -> ProfilePhoto:
    photo = ProfilePhoto()
    photo.id = uuid.uuid4()
    photo.profile_id = profile_id or uuid.uuid4()
    photo.storage_path = "profiles/uuid/original.jpg"
    photo.medium_path = "profiles/uuid/medium.jpg"
    photo.thumbnail_path = "profiles/uuid/thumbnail.jpg"
    photo.display_order = display_order
    photo.is_primary = is_primary
    photo.moderation_status = moderation_status
    photo.rejection_reason = None
    photo.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    return photo


def _make_service(repo: AsyncMock, signed_url: str = "https://signed.example/photo") -> PhotoService:
    """Create a PhotoService with mocked Firebase factories."""
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = signed_url
    mock_blob.exists.return_value = True

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    return PhotoService(
        photo_repo=repo,
        bucket_factory=lambda: mock_bucket,
        gcs_credentials_factory=lambda: MagicMock(),
    )


# ---------------------------------------------------------------------------
# register_photo
# ---------------------------------------------------------------------------

class TestRegisterPhoto:
    def _request(self, profile_id: uuid.UUID) -> PhotoRegisterRequest:
        return PhotoRegisterRequest(
            storage_path=f"profiles/{profile_id}/original.jpg",
            medium_path=f"profiles/{profile_id}/medium.jpg",
            thumbnail_path=f"profiles/{profile_id}/thumbnail.jpg",
        )

    @pytest.mark.asyncio
    async def test_registers_photo_successfully(self) -> None:
        profile_id = uuid.uuid4()
        repo = AsyncMock()
        repo.count_for_profile.return_value = 0
        created = _make_photo(profile_id=profile_id, moderation_status=ModerationStatusEnum.PENDING)
        repo.create.return_value = created

        svc = _make_service(repo)
        result = await svc.register_photo(
            profile_id=profile_id,
            owner_user_id=uuid.uuid4(),
            requesting_profile_id=profile_id,
            data=self._request(profile_id),
        )

        assert result.moderation_status == ModerationStatusEnum.PENDING
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enforces_6_photo_limit(self) -> None:
        profile_id = uuid.uuid4()
        repo = AsyncMock()
        repo.count_for_profile.return_value = MAX_PHOTOS_PER_PROFILE  # already at limit

        svc = _make_service(repo)
        with pytest.raises(BadRequestError, match="at most"):
            await svc.register_photo(
                profile_id=profile_id,
                owner_user_id=uuid.uuid4(),
                requesting_profile_id=profile_id,
                data=self._request(profile_id),
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_if_not_owner(self) -> None:
        profile_id = uuid.uuid4()
        other_profile_id = uuid.uuid4()
        repo = AsyncMock()

        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.register_photo(
                profile_id=profile_id,
                owner_user_id=uuid.uuid4(),
                requesting_profile_id=other_profile_id,
                data=self._request(profile_id),
            )

    @pytest.mark.asyncio
    async def test_raises_bad_request_if_blobs_missing(self) -> None:
        profile_id = uuid.uuid4()
        repo = AsyncMock()
        repo.count_for_profile.return_value = 0
        
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False  # Simulates missing file
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )
        
        with pytest.raises(BadRequestError, match="File not found in storage"):
            await svc.register_photo(
                profile_id=profile_id,
                owner_user_id=uuid.uuid4(),
                requesting_profile_id=profile_id,
                data=self._request(profile_id),
            )

# ---------------------------------------------------------------------------
# create_upload_session
# ---------------------------------------------------------------------------

class TestCreateUploadSession:
    @pytest.mark.asyncio
    async def test_creates_session_successfully(self) -> None:
        profile_id = uuid.uuid4()
        repo = AsyncMock()
        repo.count_for_profile.return_value = 0

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.put"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )

        session = await svc.create_upload_session(
            profile_id=profile_id,
            requesting_profile_id=profile_id,
        )

        assert session.urls.original_url == "https://signed.put"
        assert session.paths.storage_path.startswith(f"profiles/{profile_id}/")
        mock_blob.generate_signed_url.assert_called_with(
            expiration=pytest.approx(timedelta(minutes=15), abs=timedelta(seconds=1)),
            method="PUT",
            credentials=ANY,
            version="v4",
            content_type="image/jpeg",
        )

    @pytest.mark.asyncio
    async def test_raises_forbidden_if_not_owner(self) -> None:
        repo = AsyncMock()
        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.create_upload_session(
                profile_id=uuid.uuid4(),
                requesting_profile_id=uuid.uuid4(),  # Different
            )


# ---------------------------------------------------------------------------
# Tier-gated signed URL generation
# ---------------------------------------------------------------------------

class TestSignedUrls:
    def _photo(self, profile_id: uuid.UUID) -> ProfilePhoto:
        return _make_photo(
            profile_id=profile_id,
            moderation_status=ModerationStatusEnum.APPROVED,
        )

    def _svc(self) -> tuple[PhotoService, MagicMock]:
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example/x"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        repo = AsyncMock()
        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )
        return svc, mock_blob

    def test_public_tier_thumbnail_only(self) -> None:
        profile_id = uuid.uuid4()
        photo = self._photo(profile_id)
        svc, _ = self._svc()
        out = svc._build_response(photo, VisibilityTier.PUBLIC)
        assert out.signed_urls.thumbnail_url == "https://signed.example/x"
        assert out.signed_urls.medium_url is None
        assert out.signed_urls.original_url is None

    def test_registered_tier_thumbnail_and_medium(self) -> None:
        profile_id = uuid.uuid4()
        photo = self._photo(profile_id)
        svc, _ = self._svc()
        out = svc._build_response(photo, VisibilityTier.REGISTERED)
        assert out.signed_urls.thumbnail_url == "https://signed.example/x"
        assert out.signed_urls.medium_url == "https://signed.example/x"
        assert out.signed_urls.original_url is None

    def test_private_tier_all_three_urls(self) -> None:
        profile_id = uuid.uuid4()
        photo = self._photo(profile_id)
        svc, blob = self._svc()
        out = svc._build_response(photo, VisibilityTier.PRIVATE)
        assert out.signed_urls.thumbnail_url is not None
        assert out.signed_urls.medium_url is not None
        assert out.signed_urls.original_url is not None
        # generate_signed_url should have been called 3 times (thumbnail, medium, original)
        assert blob.generate_signed_url.call_count == 3

    def test_pending_photo_has_signed_urls_if_include_pending(self) -> None:
        profile_id = uuid.uuid4()
        photo = _make_photo(
            profile_id=profile_id,
            moderation_status=ModerationStatusEnum.PENDING,
        )
        svc, blob = self._svc()
        out = svc._build_response(photo, VisibilityTier.PRIVATE, include_pending=True)
        # Pending photos should have signed URLs if include_pending is True
        assert out.signed_urls.thumbnail_url is not None
        assert out.signed_urls.thumbnail_url == "https://signed.example/x"
        assert out.signed_urls.medium_url == "https://signed.example/x"
        assert out.signed_urls.original_url == "https://signed.example/x"
        assert blob.generate_signed_url.call_count == 3

    def test_signed_url_error_returns_empty_string(self) -> None:
        """If Firebase throws, the URL is '' rather than crashing the response."""
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.side_effect = Exception("Firebase error")
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        repo = AsyncMock()
        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )
        profile_id = uuid.uuid4()
        photo = _make_photo(profile_id=profile_id, moderation_status=ModerationStatusEnum.APPROVED)
        out = svc._build_response(photo, VisibilityTier.PUBLIC)
        assert out.signed_urls.thumbnail_url == ""


# ---------------------------------------------------------------------------
# list_photos
# ---------------------------------------------------------------------------

class TestListPhotos:
    @pytest.mark.asyncio
    async def test_owner_sees_pending_photos(self) -> None:
        profile_id = uuid.uuid4()
        photos = [
            _make_photo(profile_id=profile_id, moderation_status=ModerationStatusEnum.APPROVED),
            _make_photo(profile_id=profile_id, moderation_status=ModerationStatusEnum.PENDING),
        ]
        repo = AsyncMock()
        repo.list_for_profile.return_value = photos

        svc = _make_service(repo)
        result = await svc.list_photos(
            profile_id=profile_id,
            requesting_profile_id=profile_id,  # is owner
            viewer_tier=VisibilityTier.PRIVATE,
        )

        # include_pending=True was passed because requesting_profile_id == profile_id
        repo.list_for_profile.assert_awaited_once_with(profile_id, include_pending=True)
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_non_owner_sees_approved_only(self) -> None:
        profile_id = uuid.uuid4()
        other_profile_id = uuid.uuid4()
        approved_photo = _make_photo(profile_id=profile_id, moderation_status=ModerationStatusEnum.APPROVED)
        repo = AsyncMock()
        repo.list_for_profile.return_value = [approved_photo]

        svc = _make_service(repo)
        result = await svc.list_photos(
            profile_id=profile_id,
            requesting_profile_id=other_profile_id,
            viewer_tier=VisibilityTier.REGISTERED,
        )

        repo.list_for_profile.assert_awaited_once_with(profile_id, include_pending=False)
        assert result.total == 1


# ---------------------------------------------------------------------------
# delete_photo
# ---------------------------------------------------------------------------

class TestDeletePhoto:
    @pytest.mark.asyncio
    async def test_deletes_db_and_calls_firebase_delete(self) -> None:
        profile_id = uuid.uuid4()
        photo = _make_photo(profile_id=profile_id)

        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        repo = AsyncMock()
        repo.get_by_id.return_value = photo
        repo.delete.return_value = True

        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )
        await svc.delete_photo(
            photo_id=photo.id,
            profile_id=profile_id,
            requesting_profile_id=profile_id,
        )

        repo.delete.assert_awaited_once_with(photo.id)
        # Three Firebase objects (original, medium, thumbnail) should be deleted.
        assert mock_blob.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_forbidden_if_not_owner(self) -> None:
        profile_id = uuid.uuid4()
        other = uuid.uuid4()
        repo = AsyncMock()

        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.delete_photo(
                photo_id=uuid.uuid4(),
                profile_id=profile_id,
                requesting_profile_id=other,
            )

    @pytest.mark.asyncio
    async def test_raises_not_found_for_unknown_photo(self) -> None:
        profile_id = uuid.uuid4()
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        svc = _make_service(repo)
        with pytest.raises(NotFoundError):
            await svc.delete_photo(
                photo_id=uuid.uuid4(),
                profile_id=profile_id,
                requesting_profile_id=profile_id,
            )

    @pytest.mark.asyncio
    async def test_firebase_delete_failure_does_not_raise(self) -> None:
        """Firebase delete failure should be logged but not propagate."""
        profile_id = uuid.uuid4()
        photo = _make_photo(profile_id=profile_id)

        mock_blob = MagicMock()
        mock_blob.delete.side_effect = Exception("network error")
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        repo = AsyncMock()
        repo.get_by_id.return_value = photo
        repo.delete.return_value = True

        svc = PhotoService(
            photo_repo=repo,
            bucket_factory=lambda: mock_bucket,
            gcs_credentials_factory=lambda: MagicMock(),
        )
        # Should NOT raise — Firebase delete is best-effort.
        await svc.delete_photo(
            photo_id=photo.id,
            profile_id=profile_id,
            requesting_profile_id=profile_id,
        )


# ---------------------------------------------------------------------------
# set_primary
# ---------------------------------------------------------------------------

class TestSetPrimary:
    @pytest.mark.asyncio
    async def test_sets_primary_for_approved_photo(self) -> None:
        profile_id = uuid.uuid4()
        photo = _make_photo(
            profile_id=profile_id,
            moderation_status=ModerationStatusEnum.APPROVED,
        )
        repo = AsyncMock()
        repo.get_by_id.return_value = photo

        svc = _make_service(repo)
        await svc.set_primary(
            profile_id=profile_id,
            photo_id=photo.id,
            requesting_profile_id=profile_id,
        )
        repo.set_primary.assert_awaited_once_with(profile_id, photo.id)

    @pytest.mark.asyncio
    async def test_raises_bad_request_for_pending_photo(self) -> None:
        profile_id = uuid.uuid4()
        photo = _make_photo(
            profile_id=profile_id,
            moderation_status=ModerationStatusEnum.PENDING,
        )
        repo = AsyncMock()
        repo.get_by_id.return_value = photo

        svc = _make_service(repo)
        with pytest.raises(BadRequestError, match="awaiting moderation"):
            await svc.set_primary(
                profile_id=profile_id,
                photo_id=photo.id,
                requesting_profile_id=profile_id,
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_if_not_owner(self) -> None:
        repo = AsyncMock()
        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.set_primary(
                profile_id=uuid.uuid4(),
                photo_id=uuid.uuid4(),
                requesting_profile_id=uuid.uuid4(),
            )
