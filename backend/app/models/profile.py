"""
Profile ORM model.

Maps to the `profiles` table — one-to-one with `users`.
Contains all standard profile fields visible in the UI.
Sensitive fields (disability details, health, religion, contact) are in
a separate table (`sensitive_profile_data`) for data privacy (§5.2).

See Database.md §3.2 and Architecture §4.2.

Soft-delete strategy: uses SoftDeleteMixin (deleted_at), cascades with user.
"""
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    DisabilityTypeEnum,
    GenderEnum,
    MaritalStatusEnum,
    ProfileManagedByEnum,
    VerificationStatusEnum,
)


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """
    Standard profile data — everything that is NOT sensitivity-classified
    above the REGISTERED tier.

    One-to-one with `users`. The FK to users.id is UNIQUE, enforcing 1:1.
    """

    __tablename__ = "profiles"

    # --- Foreign key (1:1 with users) ---
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # --- Platform ---
    platform_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="divyang_matrimony",
        server_default="divyang_matrimony",
    )

    # --- Managed by (§2.2 dual-user reality) ---
    managed_by: Mapped[ProfileManagedByEnum] = mapped_column(
        Enum(ProfileManagedByEnum, name="profile_managed_by_enum"),
        nullable=False,
        default=ProfileManagedByEnum.SELF,
        server_default="SELF",
    )

    # --- Identity ---
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[GenderEnum] = mapped_column(
        Enum(GenderEnum, name="gender_enum"), nullable=False
    )
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    marital_status: Mapped[MaritalStatusEnum] = mapped_column(
        Enum(MaritalStatusEnum, name="marital_status_enum"), nullable=False
    )

    # --- Physical ---
    height_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # --- Professional ---
    education: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    annual_income: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Range string, not exact amount.",
    )

    # --- Language ---
    mother_tongue: Mapped[str | None] = mapped_column(String(50), nullable=True)
    languages_spoken: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Comma-separated."
    )

    # --- Location ---
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(
        String(50), nullable=False, default="India", server_default="India"
    )
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # --- Bio ---
    bio: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Free-text, max 500 chars (app-enforced)."
    )

    # --- Disability (PUBLIC tier — shown in search results) ---
    disability_type: Mapped[DisabilityTypeEnum | None] = mapped_column(
        Enum(DisabilityTypeEnum, name="disability_type_enum"),
        nullable=True,
        comment=(
            "PUBLIC tier — shown in search results (§5.2). "
            "Nullable so platforms with require_disability=false can omit it."
        ),
    )

    # --- Completeness ---
    completeness_score: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Computed on profile update; profiles < 40% excluded from search.",
    )

    # --- Visibility ---
    is_profile_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="User can hide profile from search.",
    )

    # --- Verification ---
    verification_status: Mapped[VerificationStatusEnum] = mapped_column(
        Enum(VerificationStatusEnum, name="verification_status_enum"),
        nullable=False,
        default=VerificationStatusEnum.PENDING,
        server_default="PENDING",
    )

    # --- Full-text search ---
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search index, updated via trigger (§4.4).",
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        lazy="noload",
    )
    sensitive_data: Mapped["SensitiveProfileData | None"] = relationship(  # noqa: F821
        "SensitiveProfileData",
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",
    )
    partner_preferences: Mapped["PartnerPreference | None"] = relationship(  # noqa: F821
        "PartnerPreference",
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 100",
            name="ck_profiles_completeness_score_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<Profile id={self.id} user_id={self.user_id} name={self.first_name} {self.last_name}>"
