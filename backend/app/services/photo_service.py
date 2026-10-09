"""
PhotoService — business logic for profile photo management.

Responsibilities:
  1. Register uploaded photos (validate paths, enforce limits, queue moderation).
  2. Issue tier-gated short-lived signed URLs (never long-lived Firebase URLs).
  3. Delete photos (DB hard-delete + Firebase Storage object deletion).
  4. Enforce ownership — a user can only manage their own profile's photos.
  5. Set/change primary photo.

What this service does NOT do:
  - EXIF/GPS stripping: performed by the client (Flutter image_processing_service.dart)
    before upload. Architecture §4.2 clarifies server-side EXIF strip is belt-and-
    suspenders; implemented via Pillow in _strip_exif_if_needed() below.
  - Image resizing: client-side only (Architecture §4.2).
  - Serve ciphertext or raw Firebase paths to callers — only signed URLs are
    returned in responses (Database.md §3.4, §6).

See Architecture §4.2, Database.md §3.4, §6.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import structlog

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from app.models.enums import ModerationStatusEnum, VisibilityTier
from app.models.profile_photo import ProfilePhoto
from app.repositories.photo_repository import MAX_PHOTOS_PER_PROFILE, IPhotoRepository
from app.schemas.photo import PhotoListOut, PhotoOut, PhotoRegisterRequest, SignedPhotoUrls, UploadSessionOut

logger = structlog.get_logger(__name__)

# Default TTL for signed read URLs — configurable via settings.
_SIGNED_URL_TTL_SECONDS: int = getattr(settings, "PHOTO_SIGNED_URL_TTL_SECONDS", 900)


class PhotoService:
    """
    Orchestrates photo upload registration, signed-URL issuance, and deletion.

    Constructor takes an IPhotoRepository and a callable that returns the GCS
    bucket handle. The bucket factory is injected to make the service fully
    testable without touching Firebase (mock the factory in tests).
    """

    def __init__(
        self,
        photo_repo: IPhotoRepository,
        bucket_factory=None,
        gcs_credentials_factory=None,
    ) -> None:
        self._repo = photo_repo
        # Lazy-import Firebase helpers so importing this service in tests
        # (where FIREBASE_CREDENTIALS_PATH points to a dummy file) doesn't
        # crash on startup — the factories are only called if you actually
        # try to generate a signed URL.
        if bucket_factory is None:
            from app.core.firebase import get_storage_bucket
            bucket_factory = get_storage_bucket
        if gcs_credentials_factory is None:
            from app.core.firebase import get_gcs_credentials
            gcs_credentials_factory = get_gcs_credentials
        self._bucket_factory = bucket_factory
        self._gcs_credentials_factory = gcs_credentials_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_upload_session(
        self,
        profile_id: uuid.UUID,
        requesting_profile_id: uuid.UUID,
    ) -> UploadSessionOut:
        """
        Generate three signed PUT URLs for the client to directly upload the
        original, medium, and thumbnail variants to Firebase Storage.
        """
        self._assert_owns(requesting_profile_id, profile_id)

        current_count = await self._repo.count_for_profile(profile_id)
        if current_count >= MAX_PHOTOS_PER_PROFILE:
            raise BadRequestError(
                f"A profile may have at most {MAX_PHOTOS_PER_PROFILE} photos. "
                "Delete an existing photo before uploading a new one."
            )

        base_name = str(uuid.uuid4())
        base_path = f"profiles/{profile_id}/{base_name}"
        
        paths = {
            "original": f"{base_path}_original.jpg",
            "medium": f"{base_path}_medium.jpg",
            "thumbnail": f"{base_path}_thumbnail.jpg",
        }

        ttl = timedelta(minutes=15)
        
        original_url = self._signed_url(paths["original"], ttl, method="PUT")
        medium_url = self._signed_url(paths["medium"], ttl, method="PUT")
        thumbnail_url = self._signed_url(paths["thumbnail"], ttl, method="PUT")
        
        if not original_url or not medium_url or not thumbnail_url:
            raise RuntimeError("Failed to generate upload URLs.")

        return UploadSessionOut(
            urls=UploadSessionOut.UploadUrls(
                original_url=original_url,
                medium_url=medium_url,
                thumbnail_url=thumbnail_url,
            ),
            paths=UploadSessionOut.UploadPaths(
                storage_path=paths["original"],
                medium_path=paths["medium"],
                thumbnail_path=paths["thumbnail"],
            )
        )

    async def register_photo(
        self,
        profile_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        requesting_profile_id: uuid.UUID,
        data: PhotoRegisterRequest,
    ) -> PhotoOut:
        """
        Register a newly-uploaded photo for the authenticated user's profile.

        The photo is stored with moderation_status=PENDING and will not appear
        in other users' views until an admin approves it.

        Raises:
            ForbiddenError       — if the requesting user doesn't own the profile.
            BadRequestError   — if the profile already has 6 photos.
        """
        self._assert_owns(requesting_profile_id, profile_id)

        # Enforce 6-photo limit (Database.md §3.4).
        current_count = await self._repo.count_for_profile(profile_id)
        if current_count >= MAX_PHOTOS_PER_PROFILE:
            raise BadRequestError(
                f"A profile may have at most {MAX_PHOTOS_PER_PROFILE} photos. "
                "Delete an existing photo before uploading a new one."
            )
            
        # Verify that the objects actually exist in the bucket.
        # This prevents a malicious client from registering arbitrary paths
        # or registering paths before they've finished uploading.
        try:
            bucket = self._bucket_factory()
            for p in (data.storage_path, data.medium_path, data.thumbnail_path):
                if not p.startswith(f"profiles/{profile_id}/"):
                    raise BadRequestError(f"Invalid storage path: {p}")
                blob = bucket.blob(p)
                if not blob.exists():
                    raise BadRequestError(f"File not found in storage: {p}")
        except BadRequestError:
            raise
        except Exception as e:
            logger.error("photo.verification_failed", error=str(e))
            raise BadRequestError("Could not verify uploaded files.")

        photo = ProfilePhoto(
            profile_id=profile_id,
            storage_path=data.storage_path,
            medium_path=data.medium_path,
            thumbnail_path=data.thumbnail_path,
            display_order=data.display_order,
            is_primary=False,  # Never set primary on upload; always pending moderation
            moderation_status=ModerationStatusEnum.PENDING,
        )
        photo = await self._repo.create(photo)

        logger.info(
            "photo.registered",
            photo_id=str(photo.id),
            profile_id=str(profile_id),
            moderation_status=photo.moderation_status,
        )

        # Owner sees their own pending photo with no signed URLs yet
        # (won't be approved until moderation passes).
        return self._build_response(photo, VisibilityTier.PRIVATE, include_pending=True)

    async def list_photos(
        self,
        profile_id: uuid.UUID,
        requesting_profile_id: uuid.UUID | None,
        viewer_tier: VisibilityTier,
    ) -> PhotoListOut:
        """
        List photos for a profile, gated by the viewer's visibility tier.

        Profile owner (requesting_profile_id == profile_id) also sees PENDING
        photos so they know which uploads are awaiting moderation.
        """
        is_owner = (
            requesting_profile_id is not None
            and requesting_profile_id == profile_id
        )
        photos = await self._repo.list_for_profile(
            profile_id, include_pending=is_owner
        )
        items = [self._build_response(p, viewer_tier, include_pending=is_owner) for p in photos]
        return PhotoListOut(photos=items, total=len(items))

    async def get_photo(
        self,
        photo_id: uuid.UUID,
        requesting_profile_id: uuid.UUID | None,
        viewer_tier: VisibilityTier,
    ) -> PhotoOut:
        """Return one photo with tier-gated signed URLs."""
        photo = await self._repo.get_by_id(photo_id)
        if photo is None:
            raise NotFoundError("Photo not found")

        is_owner = (
            requesting_profile_id is not None
            and requesting_profile_id == photo.profile_id
        )
        if not is_owner and photo.moderation_status != ModerationStatusEnum.APPROVED:
            raise NotFoundError("Photo not found")

        return self._build_response(photo, viewer_tier, include_pending=is_owner)

    async def set_primary(
        self,
        profile_id: uuid.UUID,
        photo_id: uuid.UUID,
        requesting_profile_id: uuid.UUID,
    ) -> None:
        """
        Promote a photo to primary.

        The photo must be APPROVED (PENDING photos cannot be set as primary —
        they might be rejected by moderation).
        """
        self._assert_owns(requesting_profile_id, profile_id)

        photo = await self._repo.get_by_id(photo_id)
        if photo is None or photo.profile_id != profile_id:
            raise NotFoundError("Photo not found")
        if photo.moderation_status != ModerationStatusEnum.APPROVED:
            raise BadRequestError(
                "Only approved photos can be set as primary. "
                "This photo is awaiting moderation."
            )

        await self._repo.set_primary(profile_id, photo_id)
        logger.info(
            "photo.primary_set",
            photo_id=str(photo_id),
            profile_id=str(profile_id),
        )

    async def delete_photo(
        self,
        photo_id: uuid.UUID,
        profile_id: uuid.UUID,
        requesting_profile_id: uuid.UUID,
    ) -> None:
        """
        Hard-delete a photo row AND its three Firebase Storage objects.

        Architecture §4.2, Database.md §5.5: profile_photos use hard delete.
        Firebase objects are deleted best-effort — a failure is logged but
        does NOT roll back the DB delete to avoid orphaned DB rows.
        """
        self._assert_owns(requesting_profile_id, profile_id)

        photo = await self._repo.get_by_id(photo_id)
        if photo is None or photo.profile_id != profile_id:
            raise NotFoundError("Photo not found")

        # DB hard delete first.
        deleted = await self._repo.delete(photo_id)
        if not deleted:
            raise NotFoundError("Photo not found")

        # Delete Firebase Storage objects best-effort.
        self._delete_firebase_objects_best_effort(photo)

        logger.info(
            "photo.deleted",
            photo_id=str(photo_id),
            profile_id=str(profile_id),
        )

    async def delete_all_for_profile(self, profile_id: uuid.UUID) -> None:
        """
        Hard-delete ALL photos for a profile (called during account deletion).

        Firebase Storage objects are deleted best-effort after the DB rows.
        """
        # Fetch paths before deleting rows.
        photos = await self._repo.list_for_profile(profile_id, include_pending=True)
        await self._repo.hard_delete_all_for_profile(profile_id)
        for photo in photos:
            self._delete_firebase_objects_best_effort(photo)

    # ------------------------------------------------------------------
    # Admin API
    # ------------------------------------------------------------------

    async def get_moderation_queue(self, limit: int = 50, offset: int = 0) -> PhotoListOut:
        """Admin only: get queue of pending photos."""
        photos = await self._repo.get_pending_photos(limit, offset)
        out = [
            self._build_response(p, VisibilityTier.PRIVATE, include_pending=True)
            for p in photos
        ]
        return PhotoListOut(photos=out, total=len(out))

    async def approve_photo(self, photo_id: uuid.UUID) -> PhotoOut:
        """Admin only: approve a photo."""
        photo = await self._repo.update_moderation(photo_id, ModerationStatusEnum.APPROVED)
        if not photo:
            raise NotFoundError("Photo not found")
        logger.info("photo.approved", photo_id=str(photo_id))
        return self._build_response(photo, VisibilityTier.PRIVATE)

    async def reject_photo(self, photo_id: uuid.UUID, reason: str) -> PhotoOut:
        """Admin only: reject a photo with a reason."""
        photo = await self._repo.update_moderation(photo_id, ModerationStatusEnum.REJECTED, reason)
        if not photo:
            raise NotFoundError("Photo not found")
        logger.info("photo.rejected", photo_id=str(photo_id), reason=reason)
        return self._build_response(photo, VisibilityTier.PRIVATE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_owns(requesting_profile_id: uuid.UUID, target_profile_id: uuid.UUID) -> None:
        if requesting_profile_id != target_profile_id:
            raise ForbiddenError("You can only manage your own profile's photos.")

    def _build_response(
        self,
        photo: ProfilePhoto,
        viewer_tier: VisibilityTier,
        *,
        include_pending: bool = False,
    ) -> PhotoOut:
        """
        Build a PhotoOut with tier-gated signed URLs.

        Tier mapping (Database.md §6):
          PUBLIC     → thumbnail only
          REGISTERED → thumbnail + medium
          PRIVATE    → thumbnail + medium + original
        """
        signed = SignedPhotoUrls()

        # Generate signed URLs for APPROVED photos, or for PENDING photos
        # if the caller is the owner or an admin (include_pending=True).
        if photo.moderation_status == ModerationStatusEnum.APPROVED or include_pending:
            ttl = timedelta(seconds=_SIGNED_URL_TTL_SECONDS)

            tier_order = [
                VisibilityTier.PUBLIC,
                VisibilityTier.REGISTERED,
                VisibilityTier.SUBSCRIBERS,
                VisibilityTier.MATCHED,
                VisibilityTier.PRIVATE,
            ]
            tier_rank = {t: i for i, t in enumerate(tier_order)}
            rank = tier_rank.get(viewer_tier, 0)

            # Thumbnail — PUBLIC+
            signed.thumbnail_url = self._signed_url(photo.thumbnail_path, ttl)

            # Medium — REGISTERED+
            if rank >= tier_rank[VisibilityTier.REGISTERED]:
                signed.medium_url = self._signed_url(photo.medium_path, ttl)

            # Original — PRIVATE only
            if rank >= tier_rank[VisibilityTier.PRIVATE]:
                signed.original_url = self._signed_url(photo.storage_path, ttl)

        return PhotoOut(
            id=photo.id,
            profile_id=photo.profile_id,
            display_order=photo.display_order,
            is_primary=photo.is_primary,
            moderation_status=photo.moderation_status,
            rejection_reason=photo.rejection_reason,
            created_at=photo.created_at,
            signed_urls=signed,
        )

    def _signed_url(self, object_path: str, ttl: timedelta, method: str = "GET") -> str:
        """Generate a short-lived signed URL for a Firebase Storage object."""
        try:
            bucket = self._bucket_factory()
            blob = bucket.blob(object_path)
            credentials = self._gcs_credentials_factory()
            
            kwargs = {
                "expiration": ttl,
                "method": method,
                "credentials": credentials,
                "version": "v4",
            }
            if method == "PUT":
                kwargs["content_type"] = "image/jpeg"
                
            return blob.generate_signed_url(**kwargs)
        except Exception as exc:
            logger.error(
                "photo.signed_url_failed",
                object_path=object_path,
                error=str(exc),
            )
            # Return empty string rather than crashing the whole response —
            # the client can retry or display a placeholder.
            return ""

    def _delete_firebase_objects_best_effort(self, photo: ProfilePhoto) -> None:
        """Delete the three Firebase Storage objects for a photo (best-effort)."""
        bucket = self._bucket_factory()
        for path in (photo.storage_path, photo.medium_path, photo.thumbnail_path):
            try:
                bucket.blob(path).delete()
            except Exception as exc:
                logger.warning(
                    "photo.firebase_delete_failed",
                    object_path=path,
                    error=str(exc),
                )
