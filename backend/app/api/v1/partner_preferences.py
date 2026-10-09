"""
Partner preferences API routes.

Implements:
    GET  /profiles/me/preferences  - Get own partner preferences
    PUT  /profiles/me/preferences  - Create or update partner preferences

Architecture §3.8: All responses use the standard envelope.
"""
import structlog
from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_current_active_user,
    get_partner_preference_service,
    get_profile_service,
)
from app.core.response import success_response
from app.models.user import User
from app.schemas.profile import PartnerPreferenceUpdateRequest
from app.services.partner_preference_service import PartnerPreferenceService
from app.services.profile_service import ProfileService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/profiles/me/preferences", tags=["Partner Preferences"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Get own partner preferences",
    description="Returns the authenticated user's partner preference settings.",
)
async def get_preferences(
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    pref_svc: PartnerPreferenceService = Depends(get_partner_preference_service),
) -> dict:
    own = await profile_svc.get_own_profile(current_user)
    profile_id = own.profile.id

    result = await pref_svc.get_preferences(profile_id)
    return success_response(
        data=result.model_dump(mode="json") if result else None,
        message="Partner preferences retrieved",
    )


@router.put(
    "",
    status_code=status.HTTP_200_OK,
    summary="Create or update partner preferences",
    description=(
        "Creates or updates partner preference settings for the authenticated user. "
        "Age range is validated against platform configuration limits."
    ),
)
async def update_preferences(
    body: PartnerPreferenceUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    profile_svc: ProfileService = Depends(get_profile_service),
    pref_svc: PartnerPreferenceService = Depends(get_partner_preference_service),
) -> dict:
    own = await profile_svc.get_own_profile(current_user)
    profile_id = own.profile.id

    result = await pref_svc.create_or_update(
        profile_id, current_user.platform_id, body
    )
    return success_response(
        data=result.model_dump(mode="json"),
        message="Partner preferences updated",
    )
