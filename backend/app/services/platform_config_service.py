"""
PlatformConfigService — reads and validates against platform_config.

Used by profile creation/update to enforce platform-specific rules
(minimum_age, require_disability) without hardcoding Divyang-specific
values into generic profile services.

See Architecture §14.2, Database.md §3.20.
"""
from datetime import date

import structlog

from app.core.exceptions import BadRequestError
from app.models.platform_config import PlatformConfig
from app.repositories.platform_config_repository import IPlatformConfigRepository

logger = structlog.get_logger(__name__)

# Fallback defaults if no platform_config row exists yet.
# This allows the system to work before the platform_config table is seeded.
_DEFAULT_SETTINGS: dict = {
    "minimum_age": 18,
    "maximum_age": 80,
    "require_disability": True,
}


class PlatformConfigService:
    """
    Platform-specific configuration lookup and validation.

    The profile service delegates platform-dependent validation to this
    service rather than hardcoding values.
    """

    def __init__(self, config_repo: IPlatformConfigRepository):
        self._repo = config_repo

    async def get_config(self, platform_id: str) -> PlatformConfig | None:
        """Get the config row for a platform. Returns None if not seeded."""
        return await self._repo.get_by_key(platform_id)

    async def get_settings(self, platform_id: str) -> dict:
        """
        Get the JSONB settings for a platform.

        Returns defaults if the platform_config row doesn't exist yet.
        """
        config = await self._repo.get_by_key(platform_id)
        if config is None:
            logger.warning(
                "platform_config_not_found_using_defaults",
                platform_id=platform_id,
            )
            return dict(_DEFAULT_SETTINGS)
        return config.settings

    async def validate_age(
        self, date_of_birth: date, platform_id: str
    ) -> None:
        """
        Validate that the user's age is within the platform's allowed range.

        Raises BadRequestError if the age is out of bounds.
        """
        settings = await self.get_settings(platform_id)
        min_age = settings.get("minimum_age", 18)
        max_age = settings.get("maximum_age", 80)

        today = date.today()
        age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1

        if age < min_age:
            raise BadRequestError(
                f"Minimum age for this platform is {min_age}. "
                f"Date of birth indicates age {age}.",
                code="AGE_TOO_YOUNG",
            )
        if age > max_age:
            raise BadRequestError(
                f"Maximum age for this platform is {max_age}. "
                f"Date of birth indicates age {age}.",
                code="AGE_TOO_OLD",
            )

    async def validate_disability_required(
        self, disability_type: str | None, platform_id: str
    ) -> None:
        """
        Validate that disability_type is set if the platform requires it.

        Divyang Matrimony requires it; Senior Citizen Matrimony does not.
        """
        settings = await self.get_settings(platform_id)
        require_disability = settings.get("require_disability", True)

        if require_disability and disability_type is None:
            raise BadRequestError(
                "Disability type is required for this platform.",
                code="DISABILITY_REQUIRED",
            )

    async def validate_preference_age_range(
        self, age_min: int | None, age_max: int | None, platform_id: str
    ) -> None:
        """
        Validate that partner preference age bounds are within platform limits.
        """
        settings = await self.get_settings(platform_id)
        plat_min = settings.get("minimum_age", 18)
        plat_max = settings.get("maximum_age", 80)

        if age_min is not None and age_min < plat_min:
            raise BadRequestError(
                f"Minimum age preference cannot be below {plat_min}.",
                code="PREF_AGE_MIN_TOO_LOW",
            )
        if age_max is not None and age_max > plat_max:
            raise BadRequestError(
                f"Maximum age preference cannot exceed {plat_max}.",
                code="PREF_AGE_MAX_TOO_HIGH",
            )
