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

import asyncio
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import structlog
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.models.enums import ModerationStatusEnum, VisibilityTier
from app.models.profile_photo import ProfilePhoto
from app.repositories.photo_repository import MAX_PHOTOS_PER_PROFILE, IPhotoRepository
from app.schemas.photo import PhotoListOut, PhotoOut, PhotoRegisterRequest, SignedPhotoUrls, UploadSessionOut

logger = structlog.get_logger(__name__)

# Formats we re-encode (stripping metadata) and the content type we store them as.
_REENCODE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# Image decoding is CPU- and memory-heavy and the storage client is blocking, so it runs on a
# small dedicated pool (PHOTO_PROCESSING_CONCURRENCY) instead of on the event loop. The pool size
# is the memory bound: at most that many images are decoded at the same time.
_image_executor: ThreadPoolExecutor | None = None


def _get_image_executor() -> ThreadPoolExecutor:
    global _image_executor
    if _image_executor is None:
        _image_executor = ThreadPoolExecutor(
            max_workers=settings.PHOTO_PROCESSING_CONCURRENCY, thread_name_prefix="photo-img"
        )
    return _image_executor

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
        max_bytes = settings.PHOTO_MAX_SIZE_MB * 1024 * 1024
        headers = {"x-goog-content-length-range": f"0,{max_bytes}"}
        
        original_url = self._signed_url(paths["original"], ttl, method="PUT", headers=headers)
        medium_url = self._signed_url(paths["medium"], ttl, method="PUT", headers=headers)
        thumbnail_url = self._signed_url(paths["thumbnail"], ttl, method="PUT", headers=headers)
        
        if not original_url or not medium_url or not thumbnail_url:
            raise ServiceUnavailableError("Failed to generate upload URLs due to a storage configuration error.")

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
            ),
            max_bytes=max_bytes,
        )

    def _verify_and_clean_variants(
        self,
        profile_id: uuid.UUID,
        upload_paths: tuple[str, str, str],
        photo_key: str,
    ) -> tuple[str, str, str]:
        """Blocking worker (runs on the image executor). Returns the final object paths.

        For each variant: confirm the object is inside this profile's folder, exists, is
        within the size limit and is a real image; strip all metadata; write the clean copy to
        `profiles/{id}/clean/...`. Only when all three succeed are the client-writable upload
        objects removed. On any failure every object this call created, and the uploads, are
        deleted so nothing half-processed stays in the bucket.
        """
        bucket = self._bucket_factory()
        prefix = f"profiles/{profile_id}/"
        server_owned = f"{prefix}clean/"
        max_bytes = settings.PHOTO_MAX_SIZE_MB * 1024 * 1024
        created: list[str] = []
        # Only objects in this profile's folder that a signed PUT URL could have produced are
        # ours to touch. `clean/` holds already-published photos; registering one of those as an
        # "upload" would delete a live photo when the upload objects are cleaned up.
        deletable = [p for p in upload_paths if p.startswith(prefix) and not p.startswith(server_owned)]
        try:
            for name, path in zip(("original", "medium", "thumbnail"), upload_paths, strict=True):
                if not path.startswith(prefix) or path.startswith(server_owned):
                    raise BadRequestError(f"Invalid storage path: {path}")
                blob = bucket.blob(path)
                if not blob.exists():
                    raise BadRequestError(f"File not found in storage: {path}")
                blob.reload()
                if blob.size is None:
                    raise BadRequestError(f"Could not verify size for {path}")
                if blob.size == 0:
                    raise BadRequestError(f"File {path} is empty or unreadable.")
                if blob.size > max_bytes:
                    raise BadRequestError(f"File {path} exceeds maximum allowed size.")
                try:
                    raw = blob.download_as_bytes()
                except Exception as exc:
                    logger.warning("photo.download_failed", object_path=path, error=str(exc))
                    raise BadRequestError(f"Could not read file {path}") from exc
                if len(raw) > max_bytes:
                    raise BadRequestError(f"File {path} exceeds maximum allowed size.")
                self._validate_image_bytes(raw[:32], path)
                clean, content_type = self._strip_metadata(raw, path)
                del raw
                final_path = f"{prefix}clean/{photo_key}_{name}.{_EXTENSIONS[content_type]}"
                # Recorded before the write so a half-finished upload is cleaned up too.
                created.append(final_path)
                bucket.blob(final_path).upload_from_string(clean, content_type=content_type)
                del clean
        except BadRequestError:
            self._delete_objects_best_effort(bucket, (*created, *deletable))
            raise
        except Exception as exc:
            self._delete_objects_best_effort(bucket, (*created, *deletable))
            logger.error("photo.verification_failed", error=str(exc))
            raise BadRequestError("Could not verify uploaded files.") from exc

        self._delete_objects_best_effort(bucket, deletable)
        return created[0], created[1], created[2]

    @staticmethod
    def _delete_objects_best_effort(bucket, paths) -> None:
        """Delete objects, logging (never raising) failures so the original error survives."""
        for path in paths:
            try:
                bucket.blob(path).delete()
            except Exception as exc:
                logger.warning("photo.object_cleanup_failed", object_path=path, error=str(exc))

    @staticmethod
    def _strip_metadata(raw: bytes, object_path: str) -> tuple[bytes, str]:
        """Re-encode an image without EXIF/GPS/XMP/ICC metadata (Architecture §4.2).

        The client strips metadata too, but it cannot be trusted. Orientation is
        applied to the pixels first so photos do not rotate. Fails closed: if the
        result still carries metadata, or the image is oversized/corrupt, the
        upload is rejected. Returns (clean_bytes, content_type).
        """
        bad = BadRequestError(f"File {object_path} is not a valid or supported image.")
        try:
            with Image.open(io.BytesIO(raw)) as img:
                fmt = img.format
                if fmt not in _REENCODE_FORMATS:
                    raise bad
                width, height = img.size
                if width * height > settings.PHOTO_MAX_PIXELS:
                    raise BadRequestError(f"File {object_path} has too many pixels.")
                img.load()
                pixels = ImageOps.exif_transpose(img)
                out = io.BytesIO()
                if fmt == "JPEG":
                    if pixels.mode not in ("RGB", "L"):
                        pixels = pixels.convert("RGB")
                    pixels.save(out, "JPEG", quality=90, optimize=True, exif=b"")
                elif fmt == "PNG":
                    pixels.save(out, "PNG", optimize=True)
                else:
                    pixels.save(out, "WEBP", quality=90, exif=b"", xmp=b"")
            clean = out.getvalue()
            with Image.open(io.BytesIO(clean)) as check:
                leaked = len(check.getexif()) > 0 or any(
                    key in check.info for key in ("exif", "xmp", "XML:com.adobe.xmp", "icc_profile")
                )
            if leaked:
                raise BadRequestError(f"File {object_path} still contains metadata after cleaning.")
            return clean, _REENCODE_FORMATS[fmt]
        except BadRequestError:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
            raise bad from exc

    @staticmethod
    def _validate_image_bytes(header: bytes, object_path: str) -> str:
        """
        Validate image format using actual binary magic bytes (not just extension/MIME).
        Supported formats: JPEG, PNG, WebP.
        """
        if len(header) >= 3 and header.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if len(header) >= 8 and header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return "webp"
        raise BadRequestError(f"File {object_path} is not a valid JPEG, PNG, or WebP image.")

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
            
        # Verify, clean and re-publish the three variants off the event loop. The cleaned
        # copies go to server-owned paths that no client-held signed PUT URL can write to,
        # so an uploader cannot swap the content after validation or moderation.
        variant_paths = (data.storage_path, data.medium_path, data.thumbnail_path)
        photo_key = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        original_path, medium_path, thumbnail_path = await loop.run_in_executor(
            _get_image_executor(),
            self._verify_and_clean_variants,
            profile_id,
            variant_paths,
            photo_key,
        )

        photo = ProfilePhoto(
            profile_id=profile_id,
            storage_path=original_path,
            medium_path=medium_path,
            thumbnail_path=thumbnail_path,
            display_order=data.display_order,
            is_primary=False,  # Never set primary on upload; always pending moderation
            moderation_status=ModerationStatusEnum.PENDING,
        )
        try:
            photo = await self._repo.create(photo)
        except Exception:
            self._delete_objects_best_effort(self._bucket_factory(), (original_path, medium_path, thumbnail_path))
            raise

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
        if photo.is_primary:
            await self._repo.promote_next_primary(profile_id)

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

    async def get_moderation_queue(
        self, limit: int = 50, offset: int = 0, *, platform_scope: str | None
    ) -> PhotoListOut:
        """Admin only: queue of pending photos.

        platform_scope is required: a platform id limits the queue to that
        platform, None (SUPER_ADMIN only) means all platforms.
        """
        photos = await self._repo.get_pending_photos(limit, offset, platform_id=platform_scope)
        out = [
            self._build_response(p, VisibilityTier.PRIVATE, include_pending=True)
            for p in photos
        ]
        return PhotoListOut(photos=out, total=len(out))

    async def approve_photo(self, photo_id: uuid.UUID, *, platform_scope: str | None) -> PhotoOut:
        """Admin only: approve a photo (404 if outside the admin's platform scope)."""
        photo = await self._repo.update_moderation(
            photo_id, ModerationStatusEnum.APPROVED, platform_id=platform_scope
        )
        if not photo:
            raise NotFoundError("Photo not found")
        logger.info("photo.approved", photo_id=str(photo_id))
        return self._build_response(photo, VisibilityTier.PRIVATE)

    async def reject_photo(
        self, photo_id: uuid.UUID, reason: str, *, platform_scope: str | None
    ) -> PhotoOut:
        """Admin only: reject a photo (404 if outside the admin's platform scope)."""
        photo = await self._repo.update_moderation(
            photo_id, ModerationStatusEnum.REJECTED, reason, platform_id=platform_scope
        )
        if not photo:
            raise NotFoundError("Photo not found")
        # A rejected photo can no longer be primary; keep the profile consistent.
        await self._repo.promote_next_primary(photo.profile_id)
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

    def _signed_url(self, object_path: str, ttl: timedelta, method: str = "GET", headers: dict[str, str] | None = None) -> str:
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
            if headers:
                kwargs["headers"] = headers

            if method == "PUT":
                kwargs["content_type"] = "image/jpeg"
                
            return blob.generate_signed_url(**kwargs)
        except Exception as exc:
            logger.error(
                "photo.signed_url_failed",
                object_path=object_path,
                error=str(exc),
            )
            # Never hand the client an empty/invalid URL as if signing worked.
            raise ServiceUnavailableError(
                "Photo storage is temporarily unavailable. Please try again shortly."
            ) from exc

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
