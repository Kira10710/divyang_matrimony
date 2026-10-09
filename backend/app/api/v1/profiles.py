"""
Profile API routes.

Implements:
    POST   /profiles           - Create profile for authenticated user
    GET    /profiles/me        - Get own profile (PRIVATE tier)
    PATCH  /profiles/me        - Update own profile
    GET    /profiles/{id}      - Get profile by ID (visibility-tier filtered)
    PUT    /profiles/me/sensitive - Update sensitive data
    GET    /profiles/me/sensitive - Get own sensitive data (decrypted)

Architecture §3.8: All responses use the standard envelope.
Route handlers are thin — validate input, call service, respond.
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Request, status

from app.core.dependencies import (
    get_current_active_user,
    get_partner_preference_service,
    get_photo_service,
    get_profile_service,
    get_request_context,
    get_sensitive_data_service,
)
from app.core.response import success_response
from app.models.enums import VisibilityTier
from app.models.user import User
from app.schemas.profile import (
    PartnerPreferenceUpdateRequest,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    SensitiveDataUpdateRequest,
)
from app.services.partner_preference_service import PartnerPreferenceService
from app.services.photo_service import PhotoService
from app.services.profile_service import ProfileService
from app.services.sensitive_data_service import SensitiveDataService
from app.services.visibility_service import filter_profile_for_tier

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


# ---------------------------------------------------------------------------
# Create profile
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create profile for authenticated user",
    description=(
        "Creates a profile for the currently authenticated user. "
        "One profile per user. Returns 409 if a profile already exists."
    ),
)
async def create_profile(
    body: ProfileCreateRequest,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
) -> dict:
    profile = await profile_svc.create_profile(current_user, body)
    profile_out = filter_profile_for_tier(profile, VisibilityTier.PRIVATE)
    return success_response(
        data=profile_out.model_dump(mode="json"),
        message="Profile created successfully",
    )


# ---------------------------------------------------------------------------
# Get own profile
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get own profile (full data)",
    description=(
        "Returns the authenticated user's complete profile including "
        "decrypted sensitive data and partner preferences (PRIVATE tier)."
    ),
)
async def get_own_profile(
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    pref_svc: PartnerPreferenceService = Depends(get_partner_preference_service),
    photo_svc: PhotoService = Depends(get_photo_service),
) -> dict:
    result = await profile_svc.get_own_profile(current_user)
    profile_id = result.profile.id

    # Fetch partner preferences
    prefs = await pref_svc.get_preferences(profile_id)
    result.partner_preferences = prefs

    # Fetch photos (owner sees pending photos too)
    photos_list = await photo_svc.list_photos(
        profile_id=profile_id,
        requesting_profile_id=profile_id,
        viewer_tier=VisibilityTier.PRIVATE,
    )
    result.profile.photos = photos_list.photos

    return success_response(
        data=result.model_dump(mode="json"),
        message="Profile retrieved",
    )


# ---------------------------------------------------------------------------
# Update own profile
# ---------------------------------------------------------------------------

@router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Update own profile",
    description=(
        "Updates the authenticated user's profile. Only provided fields "
        "are updated (PATCH semantics). Completeness score is recalculated."
    ),
)
async def update_own_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
) -> dict:
    profile = await profile_svc.update_profile(current_user, body)
    profile_out = filter_profile_for_tier(profile, VisibilityTier.PRIVATE)
    return success_response(
        data=profile_out.model_dump(mode="json"),
        message="Profile updated successfully",
    )


# ---------------------------------------------------------------------------
# Get profile by ID (another user's profile, visibility-filtered)
# ---------------------------------------------------------------------------

@router.get(
    "/{profile_id}",
    status_code=status.HTTP_200_OK,
    summary="Get profile by ID",
    description=(
        "Returns a profile filtered to the viewer's visibility tier. "
        "Fields above the viewer's access level are set to null."
    ),
)
async def get_profile_by_id(
    profile_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    photo_svc: PhotoService = Depends(get_photo_service),
) -> dict:
    # TODO: Wire has_active_subscription and has_mutual_interest from
    # subscription and interest services when those modules are implemented.
    profile_out = await profile_svc.get_profile_by_id(
        profile_id,
        current_user,
        has_active_subscription=False,
        has_mutual_interest=False,
    )

    # Determine viewer's profile ID
    try:
        viewer = await profile_svc.get_own_profile(current_user)
        viewer_profile_id = viewer.profile.id
    except Exception:
        viewer_profile_id = None

    # Fetch photos for the viewer's tier
    photos_list = await photo_svc.list_photos(
        profile_id=profile_id,
        requesting_profile_id=viewer_profile_id,
        viewer_tier=profile_out.visibility_tier,
    )
    profile_out.photos = photos_list.photos

    return success_response(
        data=profile_out.model_dump(mode="json"),
        message="Profile retrieved",
    )


# ---------------------------------------------------------------------------
# Sensitive data
# ---------------------------------------------------------------------------

@router.get(
    "/me/sensitive",
    status_code=status.HTTP_200_OK,
    summary="Get own sensitive profile data",
    description=(
        "Returns the authenticated user's sensitive profile data (decrypted). "
        "Only accessible by the profile owner."
    ),
)
async def get_own_sensitive_data(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    sensitive_svc: SensitiveDataService = Depends(get_sensitive_data_service),
) -> dict:
    ctx = get_request_context(request)
    # Get the user's profile ID
    profile_data = await profile_svc.get_own_profile(current_user)
    profile_id = profile_data.profile.id

    result = await sensitive_svc.get_decrypted(
        profile_id,
        viewer_user_id=current_user.id,
        tier=VisibilityTier.PRIVATE,
        ip_address=ctx["ip_address"],
        platform_id=current_user.platform_id,
    )
    return success_response(
        data=result.model_dump(mode="json") if result else None,
        message="Sensitive data retrieved",
    )


@router.put(
    "/me/sensitive",
    status_code=status.HTTP_200_OK,
    summary="Update sensitive profile data",
    description=(
        "Creates or updates the authenticated user's sensitive profile data. "
        "Fields are encrypted before storage. Completeness score is recalculated."
    ),
)
async def update_sensitive_data(
    body: SensitiveDataUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    sensitive_svc: SensitiveDataService = Depends(get_sensitive_data_service),
) -> dict:
    # Get the user's profile
    own = await profile_svc.get_own_profile(current_user)
    profile_id = own.profile.id

    # Create or update sensitive data
    data = body.model_dump(exclude_unset=True)
    await sensitive_svc.create_or_update(profile_id, data)

    # Recalculate completeness (sensitive fields contribute to the score)
    new_score = await profile_svc.recalculate_completeness(profile_id)

    return success_response(
        data={"completeness_score": new_score},
        message="Sensitive data updated successfully",
    )


# ---------------------------------------------------------------------------
# Partner Preferences
# ---------------------------------------------------------------------------

@router.get(
    "/me/partner-preferences",
    status_code=status.HTTP_200_OK,
    summary="Get own partner preferences",
    description=(
        "Returns the authenticated user's partner preferences. "
        "Returns None if not yet created."
    ),
)
async def get_own_partner_preferences(
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    pref_svc: PartnerPreferenceService = Depends(get_partner_preference_service),
) -> dict:
    own = await profile_svc.get_own_profile(current_user)
    result = await pref_svc.get_preferences(own.profile.id)
    return success_response(
        data=result.model_dump(mode="json") if result else None,
        message="Partner preferences retrieved",
    )


@router.put(
    "/me/partner-preferences",
    status_code=status.HTTP_200_OK,
    summary="Update partner preferences",
    description=(
        "Creates or updates the authenticated user's partner preferences. "
        "Recalculates completeness score."
    ),
)
async def update_own_partner_preferences(
    body: PartnerPreferenceUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    pref_svc: PartnerPreferenceService = Depends(get_partner_preference_service),
) -> dict:
    own = await profile_svc.get_own_profile(current_user)
    profile_id = own.profile.id

    await pref_svc.create_or_update(
        profile_id, current_user.platform_id, body
    )

    new_score = await profile_svc.recalculate_completeness(profile_id)

    return success_response(
        data={"completeness_score": new_score},
        message="Partner preferences updated successfully",
    )
