"""
PartnerPreferenceService — manages partner preferences.

See Architecture §4.3, Database.md §3.5.
"""
import uuid

import structlog

from app.repositories.partner_preference_repository import IPartnerPreferenceRepository
from app.schemas.profile import PartnerPreferenceOut, PartnerPreferenceUpdateRequest
from app.services.platform_config_service import PlatformConfigService

logger = structlog.get_logger(__name__)


class PartnerPreferenceService:
    """Manages partner preference CRUD with platform validation."""

    def __init__(
        self,
        pref_repo: IPartnerPreferenceRepository,
        platform_svc: PlatformConfigService,
    ):
        self._repo = pref_repo
        self._platform_svc = platform_svc

    async def get_preferences(
        self, profile_id: uuid.UUID
    ) -> PartnerPreferenceOut | None:
        """Get partner preferences for a profile. Returns None if not set."""
        pref = await self._repo.get_by_profile_id(profile_id)
        if pref is None:
            return None
        return PartnerPreferenceOut.model_validate(pref)

    async def create_or_update(
        self,
        profile_id: uuid.UUID,
        platform_id: str,
        data: PartnerPreferenceUpdateRequest,
    ) -> PartnerPreferenceOut:
        """
        Create or update partner preferences for a profile.

        Validates age range against platform_config limits.
        """
        update_data = data.model_dump(exclude_unset=True)

        # Validate age range against platform config
        age_min = update_data.get("age_min")
        age_max = update_data.get("age_max")
        if age_min is not None or age_max is not None:
            await self._platform_svc.validate_preference_age_range(
                age_min, age_max, platform_id
            )

        existing = await self._repo.get_by_profile_id(profile_id)
        if existing is None:
            update_data["profile_id"] = profile_id
            pref = await self._repo.create(update_data)
            logger.info("partner_preferences_created", profile_id=str(profile_id))
        else:
            pref = await self._repo.update(existing, update_data)
            logger.info("partner_preferences_updated", profile_id=str(profile_id))

        return PartnerPreferenceOut.model_validate(pref)
