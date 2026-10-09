"""
ProfileService — core profile business logic.

Orchestrates:
  - Profile creation (with platform validation + completeness scoring)
  - Profile update (ownership check + completeness recalc)
  - Profile retrieval (with visibility-tier filtering)
  - Profile ownership validation

Services never commit — the route handler's `get_db` dependency
commits on success, rolls back on exception.

See Architecture §4.2.
"""
import uuid

import structlog

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import VisibilityTier
from app.models.profile import Profile
from app.models.user import User
from app.repositories.profile_repository import IProfileRepository
from app.schemas.profile import (
    ProfileCreateRequest,
    ProfileOut,
    ProfileUpdateRequest,
    ProfileWithSensitiveOut,
)
from app.services.completeness_service import calculate_completeness
from app.services.platform_config_service import PlatformConfigService
from app.services.sensitive_data_service import SensitiveDataService
from app.services.visibility_service import (
    filter_profile_for_tier,
    resolve_visibility_tier,
)

logger = structlog.get_logger(__name__)


class ProfileService:
    """
    Profile management service.

    Constructor injection: all dependencies are injected, keeping
    this class testable without a real DB.
    """

    def __init__(
        self,
        profile_repo: IProfileRepository,
        sensitive_svc: SensitiveDataService,
        platform_svc: PlatformConfigService,
    ):
        self._profile_repo = profile_repo
        self._sensitive_svc = sensitive_svc
        self._platform_svc = platform_svc

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    async def create_profile(
        self,
        user: User,
        data: ProfileCreateRequest,
    ) -> Profile:
        """
        Create a profile for the authenticated user.

        Business rules:
        - One profile per user (ConflictError if exists)
        - Age validated against platform_config.minimum_age/maximum_age
        - Disability required if platform_config.require_disability = True
        - Completeness score computed immediately
        """
        # Check no existing profile
        if await self._profile_repo.exists_for_user(user.id):
            raise ConflictError("Profile already exists for this user")

        # Platform-specific validation
        await self._platform_svc.validate_age(data.date_of_birth, user.platform_id)
        disability_val = data.disability_type.value if data.disability_type else None
        await self._platform_svc.validate_disability_required(
            disability_val, user.platform_id
        )

        # Build profile data
        profile_data = data.model_dump()
        profile_data["user_id"] = user.id
        profile_data["platform_id"] = user.platform_id

        # Create the profile
        profile = await self._profile_repo.create(profile_data)

        # Compute completeness score (no sensitive data yet on first create)
        score = calculate_completeness(profile, sensitive_data=None)
        profile = await self._profile_repo.update(
            profile, {"completeness_score": score}
        )

        logger.info(
            "profile_created",
            user_id=str(user.id),
            profile_id=str(profile.id),
            completeness_score=score,
        )
        return profile

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    async def update_profile(
        self,
        user: User,
        data: ProfileUpdateRequest,
    ) -> Profile:
        """
        Update the authenticated user's profile.

        Only the profile owner can update. Recalculates completeness
        after every update.
        """
        profile = await self._get_own_profile(user)

        # Only set fields that were actually provided
        update_data = data.model_dump(exclude_unset=True)

        # Validate age if date_of_birth is being changed
        if "date_of_birth" in update_data and update_data["date_of_birth"] is not None:
            await self._platform_svc.validate_age(
                update_data["date_of_birth"], profile.platform_id
            )

        # Validate disability if being changed
        if "disability_type" in update_data:
            dt_val = update_data["disability_type"]
            disability_val = dt_val.value if dt_val else None
            await self._platform_svc.validate_disability_required(
                disability_val, profile.platform_id
            )

        profile = await self._profile_repo.update(profile, update_data)

        # Recompute completeness
        sensitive_data = await self._sensitive_svc.get_for_profile(profile.id)
        score = calculate_completeness(profile, sensitive_data)
        if score != profile.completeness_score:
            profile = await self._profile_repo.update(
                profile, {"completeness_score": score}
            )

        logger.info(
            "profile_updated",
            profile_id=str(profile.id),
            completeness_score=score,
        )
        return profile

    # -----------------------------------------------------------------------
    # Get own profile
    # -----------------------------------------------------------------------

    async def get_own_profile(
        self,
        user: User,
    ) -> ProfileWithSensitiveOut:
        """
        Get the authenticated user's complete profile (PRIVATE tier).

        Returns profile + decrypted sensitive data + partner preferences.
        """
        profile = await self._get_own_profile(user)

        # Build the response at PRIVATE tier
        profile_out = filter_profile_for_tier(profile, VisibilityTier.PRIVATE)

        # Get decrypted sensitive data (PRIVATE = all fields)
        sensitive_out = await self._sensitive_svc.get_decrypted(
            profile.id,
            viewer_user_id=user.id,
            tier=VisibilityTier.PRIVATE,
            platform_id=profile.platform_id,
        )

        pref_out = None

        return ProfileWithSensitiveOut(
            profile=profile_out,
            sensitive_data=sensitive_out,
            partner_preferences=pref_out,
        )

    # -----------------------------------------------------------------------
    # Get profile by ID (for viewing another user's profile)
    # -----------------------------------------------------------------------

    async def get_profile_by_id(
        self,
        profile_id: uuid.UUID,
        viewer: User,
        *,
        has_active_subscription: bool = False,
        has_mutual_interest: bool = False,
        ip_address: str | None = None,
    ) -> ProfileOut:
        """
        Get a profile by ID with visibility-tier filtering.

        The returned ProfileOut only contains fields the viewer is
        allowed to see. Sensitive data is NOT included in this response —
        it's accessed via a separate endpoint.
        """
        profile = await self._profile_repo.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError("Profile not found")

        tier = resolve_visibility_tier(
            viewer,
            profile,
            has_active_subscription=has_active_subscription,
            has_mutual_interest=has_mutual_interest,
        )

        return filter_profile_for_tier(profile, tier)

    # -----------------------------------------------------------------------
    # Recalculate completeness (called after sensitive data update)
    # -----------------------------------------------------------------------

    async def recalculate_completeness(self, profile_id: uuid.UUID) -> int:
        """
        Recalculate and update the completeness score for a profile.

        Called by the sensitive_data update endpoint after modifying
        sensitive fields that contribute to the score.
        """
        profile = await self._profile_repo.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError("Profile not found")

        sensitive_data = await self._sensitive_svc.get_for_profile(profile_id)
        score = calculate_completeness(profile, sensitive_data)

        if score != profile.completeness_score:
            await self._profile_repo.update(
                profile, {"completeness_score": score}
            )

        return score

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _get_own_profile(self, user: User) -> Profile:
        """
        Get the profile belonging to the authenticated user.

        Raises NotFoundError if no profile exists.
        """
        profile = await self._profile_repo.get_by_user_id(user.id)
        if profile is None:
            raise NotFoundError("No profile found. Please create a profile first.")
        return profile
