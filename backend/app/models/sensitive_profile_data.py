"""
SensitiveProfileData ORM model.

Separated from `profiles` for data privacy (Architecture §5.2, §8.3).
Contains fields that:
- Have restricted visibility (SUBSCRIBERS / MATCHED / PRIVATE tiers)
- Require field-level AES-256-GCM encryption (Database.md §3.3 note)
- Generate access logs when read (sensitive_data_access_logs)

See Database.md §3.3.

Soft-delete strategy: uses SoftDeleteMixin (deleted_at), cascades with profile.

ENCRYPTED fields (6 total):
  disability_details, health_conditions, about_family,
  contact_phone, contact_email, whatsapp_number

All encrypted columns are stored as TEXT — base64-encoded AES-256-GCM
ciphertext (nonce + tag + payload) is far larger than the plaintext.
"""
import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SensitiveProfileData(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Sensitivity-classified profile fields — 1:1 with profiles.

    Access to this table is logged in sensitive_data_access_logs (§5.6).
    The encryption/decryption boundary lives in the service layer
    (sensitive_data_service.py), not in the ORM model — the model stores
    ciphertext as-is; the service encrypts before write and decrypts after read.
    """

    __tablename__ = "sensitive_profile_data"

    # --- Foreign key (1:1 with profiles) ---
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # --- Disability details (SUBSCRIBERS tier) ---
    disability_percentage: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="UDID percentage (0–100).",
    )
    disability_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — free-text description. MATCHED tier.",
    )
    disability_since: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Birth / childhood / acquired. SUBSCRIBERS tier.",
    )
    mobility_aid: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Wheelchair, crutches, etc. SUBSCRIBERS tier.",
    )

    # --- Health (MATCHED tier) ---
    health_conditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — other health conditions. MATCHED tier.",
    )

    # --- Religion/caste (SUBSCRIBERS tier) ---
    religion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    caste: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sub_caste: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Family (SUBSCRIBERS tier, except about_family which is MATCHED) ---
    family_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Joint / Nuclear."
    )
    family_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Middle / Upper-Middle / Affluent."
    )
    father_occupation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mother_occupation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    siblings: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Count and married/unmarried."
    )
    about_family: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — free-text family description. MATCHED tier.",
    )

    # --- Contact (MATCHED tier — visible only on mutual interest) ---
    contact_phone: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — visible only on mutual interest.",
    )
    contact_email: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — visible only on mutual interest.",
    )
    whatsapp_number: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ENCRYPTED — for WhatsApp handoff (§4.6). MATCHED tier.",
    )

    # --- Relationships ---
    profile: Mapped["Profile"] = relationship(  # noqa: F821
        "Profile",
        back_populates="sensitive_data",
        lazy="noload",
    )

    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "disability_percentage IS NULL OR "
            "(disability_percentage >= 0 AND disability_percentage <= 100)",
            name="ck_sensitive_profile_data_disability_pct_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<SensitiveProfileData id={self.id} profile_id={self.profile_id}>"
