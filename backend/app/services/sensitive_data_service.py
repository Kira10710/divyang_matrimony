"""
SensitiveDataService — manages encrypted sensitive profile fields.

Responsibilities:
  - Encrypts plaintext fields before writing to the repository
  - Decrypts ciphertext fields after reading from the repository
  - Logs access to sensitive_data_access_logs (§5.6)
  - Filters returned fields based on visibility tier

The encryption/decryption boundary is HERE, not in the ORM model.
The repository stores and retrieves ciphertext; this service
transforms between plaintext (API layer) and ciphertext (storage layer).
"""
import uuid

import structlog

from app.core.encryption import (
    decrypt_sensitive_dict,
    encrypt_sensitive_dict,
)
from app.models.enums import VisibilityTier
from app.models.sensitive_profile_data import SensitiveProfileData
from app.repositories.sensitive_data_repository import ISensitiveDataRepository
from app.schemas.profile import SensitiveDataOut
from app.services.visibility_service import get_allowed_sensitive_fields

logger = structlog.get_logger(__name__)


class SensitiveDataService:
    """Manages sensitive profile data with encryption and access logging."""

    def __init__(self, sensitive_repo: ISensitiveDataRepository):
        self._repo = sensitive_repo

    async def get_for_profile(
        self,
        profile_id: uuid.UUID,
    ) -> SensitiveProfileData | None:
        """Get raw (ciphertext) sensitive data row — for internal use only."""
        return await self._repo.get_by_profile_id(profile_id)

    async def get_decrypted(
        self,
        profile_id: uuid.UUID,
        *,
        viewer_user_id: uuid.UUID,
        tier: VisibilityTier,
        ip_address: str | None = None,
        platform_id: str = "divyang_matrimony",
    ) -> SensitiveDataOut | None:
        """
        Get sensitive data, decrypted and filtered to the viewer's tier.

        Logs the access if the tier is SUBSCRIBERS or higher.
        Returns None if no sensitive data exists for this profile.
        """
        record = await self._repo.get_by_profile_id(profile_id)
        if record is None:
            return None

        allowed_fields = get_allowed_sensitive_fields(tier)
        if not allowed_fields:
            return None

        # Build a dict of the allowed fields, decrypt encrypted ones
        raw_data: dict = {}
        for field_name in allowed_fields:
            raw_data[field_name] = getattr(record, field_name, None)

        # Decrypt the encrypted fields that are in the allowed set
        decrypted = decrypt_sensitive_dict(raw_data)

        # Log access (only for SUBSCRIBERS+ tiers, not PUBLIC/REGISTERED)
        accessed_field_names = [f for f in allowed_fields if decrypted.get(f) is not None]
        if accessed_field_names:
            await self._repo.log_access(
                accessor_user_id=viewer_user_id,
                target_profile_id=profile_id,
                fields_accessed=accessed_field_names,
                access_tier=tier.value,
                ip_address=ip_address,
                platform_id=platform_id,
            )

        return SensitiveDataOut(
            id=record.id,
            profile_id=record.profile_id,
            **decrypted,
        )

    async def create_or_update(
        self,
        profile_id: uuid.UUID,
        data: dict,
    ) -> SensitiveProfileData:
        """
        Create or update sensitive data for a profile.

        Input `data` contains plaintext values.
        This method encrypts before persisting.
        """
        # Encrypt fields before storage
        encrypted_data = encrypt_sensitive_dict(data)

        existing = await self._repo.get_by_profile_id(profile_id)
        if existing is None:
            encrypted_data["profile_id"] = profile_id
            record = await self._repo.create(encrypted_data)
            logger.info("sensitive_data_created", profile_id=str(profile_id))
        else:
            record = await self._repo.update(existing, encrypted_data)
            logger.info("sensitive_data_updated", profile_id=str(profile_id))

        return record
