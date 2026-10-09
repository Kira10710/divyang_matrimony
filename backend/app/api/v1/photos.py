"""
Photo API routes.

Implements:
    POST   /profiles/me/photos                  — Register uploaded photo paths
    GET    /profiles/me/photos                  — List own photos (incl. PENDING)
    GET    /profiles/{id}/photos                — List another profile's photos (APPROVED only, tier-gated)
    DELETE /profiles/me/photos/{photo_id}       — Hard-delete own photo
    PATCH  /profiles/me/photos/{photo_id}/primary — Set as primary

Architecture §4.2, Database.md §3.4, §6.

Route handlers are thin: authenticate → resolve profile → call service → respond.
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_current_active_user,
    get_photo_service,
    get_profile_repository,
)
from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.models.enums import VisibilityTier
from app.models.user import User
from app.schemas.photo import PhotoRegisterRequest
from app.services.photo_service import PhotoService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Photos"])


# ---------------------------------------------------------------------------
# Helper: resolve caller's profile_id or raise
# ---------------------------------------------------------------------------

async def _resolve_own_profile_id(
    current_user: User,
    profile_repo,
) -> uuid.UUID:
    """Look up the signed-in user's profile. Raises 404 if no profile yet."""
    profile = await profile_repo.get_by_user_id(current_user.id)
    if profile is None:
        raise NotFoundError("You don't have a profile yet. Create one first.")
    return profile.id


# ---------------------------------------------------------------------------
# POST /profiles/me/photos/upload-sessions — request signed upload URLs
# ---------------------------------------------------------------------------

@router.post(
    "/profiles/me/photos/upload-sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Create upload session",
    description=(
        "Returns signed PUT URLs for the client to directly upload the "
        "original, medium, and thumbnail variants to Firebase Storage."
    ),
)
async def create_upload_session(
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    profile_id = await _resolve_own_profile_id(current_user, profile_repo)
    session = await photo_svc.create_upload_session(
        profile_id=profile_id,
        requesting_profile_id=profile_id,
    )
    return success_response(
        data=session.model_dump(),
        message="Upload session created.",
    )


# ---------------------------------------------------------------------------
# POST /profiles/me/photos — register an uploaded photo
# ---------------------------------------------------------------------------

@router.post(
    "/profiles/me/photos",
    status_code=status.HTTP_201_CREATED,
    summary="Register uploaded photo paths",
    description=(
        "After the client uploads all three image variants (original, medium, "
        "thumbnail) to Firebase Storage, it calls this endpoint to register the "
        "storage paths. The photo enters moderation (PENDING) and is only visible "
        "to viewers once an admin approves it."
    ),
)
async def register_photo(
    body: PhotoRegisterRequest,
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    profile_id = await _resolve_own_profile_id(current_user, profile_repo)
    photo = await photo_svc.register_photo(
        profile_id=profile_id,
        owner_user_id=current_user.id,
        requesting_profile_id=profile_id,
        data=body,
    )
    return success_response(
        data=photo.model_dump(),
        message="Photo registered and queued for moderation.",
    )


# ---------------------------------------------------------------------------
# GET /profiles/me/photos — list own photos (incl. PENDING)
# ---------------------------------------------------------------------------

@router.get(
    "/profiles/me/photos",
    summary="List own profile photos",
    description=(
        "Returns all photos for the authenticated user's profile, including "
        "PENDING ones (so the owner can see upload status). REJECTED photos "
        "are omitted. Tier = PRIVATE so signed_urls includes all three variants."
    ),
)
async def list_own_photos(
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    profile_id = await _resolve_own_profile_id(current_user, profile_repo)
    result = await photo_svc.list_photos(
        profile_id=profile_id,
        requesting_profile_id=profile_id,
        viewer_tier=VisibilityTier.PRIVATE,
    )
    return success_response(data=result.model_dump(), message="Success")


# ---------------------------------------------------------------------------
# GET /profiles/{profile_id}/photos — list another profile's APPROVED photos
# ---------------------------------------------------------------------------

@router.get(
    "/profiles/{profile_id}/photos",
    summary="List profile photos (tier-gated)",
    description=(
        "Returns APPROVED photos for any profile. The signed URL variants "
        "populated depend on the viewer's tier:\n"
        "  PUBLIC → thumbnail only\n"
        "  REGISTERED → thumbnail + medium\n"
        "  PRIVATE (own profile) → thumbnail + medium + original\n"
        "PENDING and REJECTED photos are never returned for other users."
    ),
)
async def list_profile_photos(
    profile_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    # Resolve the viewer's own profile (if any) to determine tier.
    viewer_profile = await profile_repo.get_by_user_id(current_user.id)
    viewer_profile_id = viewer_profile.id if viewer_profile else None

    # Tier resolution: owner → PRIVATE; everyone else → REGISTERED
    # (Full tier logic — SUBSCRIBERS, MATCHED — belongs in a future
    # subscription-aware tier resolver. For now we use REGISTERED as the
    # floor for authenticated non-owner viewers, per Architecture §6.)
    if viewer_profile_id == profile_id:
        tier = VisibilityTier.PRIVATE
    else:
        tier = VisibilityTier.REGISTERED

    result = await photo_svc.list_photos(
        profile_id=profile_id,
        requesting_profile_id=viewer_profile_id,
        viewer_tier=tier,
    )
    return success_response(data=result.model_dump(), message="Success")


# ---------------------------------------------------------------------------
# DELETE /profiles/me/photos/{photo_id} — hard-delete own photo
# ---------------------------------------------------------------------------

@router.delete(
    "/profiles/me/photos/{photo_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete own photo",
    description=(
        "Permanently deletes the photo row from the database and the three "
        "Firebase Storage objects (best-effort). Hard delete — no soft delete "
        "for photos (Database.md §5.5)."
    ),
)
async def delete_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    profile_id = await _resolve_own_profile_id(current_user, profile_repo)
    await photo_svc.delete_photo(
        photo_id=photo_id,
        profile_id=profile_id,
        requesting_profile_id=profile_id,
    )
    return success_response(message="Photo deleted.")


# ---------------------------------------------------------------------------
# PATCH /profiles/me/photos/{photo_id}/primary — set primary photo
# ---------------------------------------------------------------------------

@router.patch(
    "/profiles/me/photos/{photo_id}/primary",
    summary="Set photo as primary",
    description=(
        "Promotes the given photo to the profile's primary display photo. "
        "The photo must be APPROVED (pending moderation photos cannot be "
        "set as primary). Clears is_primary on all other photos atomically."
    ),
)
async def set_primary_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    photo_svc: PhotoService = Depends(get_photo_service),
    profile_repo=Depends(get_profile_repository),
):
    profile_id = await _resolve_own_profile_id(current_user, profile_repo)
    await photo_svc.set_primary(
        profile_id=profile_id,
        photo_id=photo_id,
        requesting_profile_id=profile_id,
    )
    return success_response(message="Primary photo updated.")
