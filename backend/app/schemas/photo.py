"""
Photo Pydantic schemas — request validation and response serialization.

Design:
  - Responses never include Firebase download URLs (long-lived URLs bypass
    tier checks). Instead, a *signed_urls* dict is populated by the service
    per-request. DB paths are never exposed in API responses.
  - Which variant(s) are populated in signed_urls depends on the viewer's
    visibility tier (Architecture §4.2, Database.md §6):
      PUBLIC     → thumbnail_url only
      REGISTERED → thumbnail_url + medium_url
      PRIVATE    → thumbnail_url + medium_url + original_url
  - Pending photos are only included in the owner's own-photo list
    (moderation_status is exposed to the owner for UI feedback).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ModerationStatusEnum

# --------------------------------------------------------------------------
# Request schemas
# --------------------------------------------------------------------------


class PhotoRegisterRequest(BaseModel):
    """
    POST /profiles/me/photos

    The client (Flutter) has already uploaded all three variants to Firebase
    Storage and sends their object paths here for the backend to store.
    The backend validates paths look reasonable, strips EXIF, and queues
    the photo for moderation.
    """

    storage_path: str = Field(
        ...,
        max_length=500,
        description="Firebase Storage object path of the original (~1600 px).",
    )
    medium_path: str = Field(
        ...,
        max_length=500,
        description="Firebase Storage object path of the 800 px variant.",
    )
    thumbnail_path: str = Field(
        ...,
        max_length=500,
        description="Firebase Storage object path of the 200 px variant.",
    )
    display_order: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Sort position (0–5). Must be unique within the profile.",
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is the profile's primary display photo.",
    )

    @field_validator("storage_path", "medium_path", "thumbnail_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Path must not be empty")
        # Paths should not look like full HTTP URLs — they are GCS object paths.
        if v.startswith("http://") or v.startswith("https://"):
            raise ValueError(
                "Provide a Firebase Storage object path, not a download URL. "
                "Example: 'profiles/uuid/photo_original.jpg'"
            )
        return v


class SetPrimaryPhotoRequest(BaseModel):
    """PATCH /profiles/me/photos/{photo_id}/primary — promote a photo to primary."""
    pass  # No body needed; the photo_id is in the URL path.


class UploadSessionOut(BaseModel):
    """
    Response for POST /profiles/me/photos/upload-sessions
    Provides signed PUT URLs and the exact GCS object paths to use in the registration request.
    """
    class UploadUrls(BaseModel):
        original_url: str
        medium_url: str
        thumbnail_url: str
        
    class UploadPaths(BaseModel):
        storage_path: str
        medium_path: str
        thumbnail_path: str
        
    urls: UploadUrls
    paths: UploadPaths

# --------------------------------------------------------------------------
# Response schemas
# --------------------------------------------------------------------------


class SignedPhotoUrls(BaseModel):
    """
    Short-lived signed read URLs issued per-request.

    Which fields are populated depends on the viewer's tier:
      PUBLIC     → thumbnail_url
      REGISTERED → thumbnail_url + medium_url
      PRIVATE    → thumbnail_url + medium_url + original_url
    """

    thumbnail_url: str | None = None
    medium_url: str | None = None
    original_url: str | None = None


class PhotoOut(BaseModel):
    """
    Photo metadata returned in API responses.

    DB paths are NOT included — only signed_urls, which expire after
    PHOTO_SIGNED_URL_TTL_SECONDS (default: 900 s / 15 min).
    """

    id: uuid.UUID
    profile_id: uuid.UUID
    display_order: int
    is_primary: bool
    moderation_status: ModerationStatusEnum
    rejection_reason: str | None = None
    created_at: datetime

    # Populated by PhotoService.build_photo_response() per-request.
    signed_urls: SignedPhotoUrls = Field(default_factory=SignedPhotoUrls)

    model_config = {"from_attributes": True}


class PhotoListOut(BaseModel):
    """Response for GET /profiles/{id}/photos and /profiles/me/photos."""

    photos: list[PhotoOut]
    total: int


class PhotoModerationRejectRequest(BaseModel):
    """Payload for rejecting a photo."""

    rejection_reason: str = Field(..., max_length=500, min_length=5)
