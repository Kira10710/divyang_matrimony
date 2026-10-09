"""
PartnerPreference ORM model.

One-to-one with `profiles`. Stores the user's filter criteria for
matching/search (Architecture §4.3, §4.5).

See Database.md §3.5.

No soft-delete — deleted with profile via CASCADE.
No deleted_at column on this table.
"""
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    DisabilityTypeEnum,
    GenderEnum,
    MaritalStatusEnum,
)


class PartnerPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Partner preference criteria — 1:1 with profiles.

    Used by matching/search to filter and rank candidate profiles.

    Age bounds are validated at the application layer against
    platform_config.settings, NOT as database CHECK constraints.
    Only internal consistency (age_min <= age_max) is enforced at DB level.
    """

    __tablename__ = "partner_preferences"

    # --- Foreign key (1:1 with profiles) ---
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # --- Gender (hard filter) ---
    preferred_gender: Mapped[GenderEnum | None] = mapped_column(
        Enum(GenderEnum, name="gender_enum", create_type=False),
        nullable=True,
    )

    # --- Age range (hard filter — bounds from platform_config) ---
    age_min: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    age_max: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # --- Height range (soft filter) ---
    preferred_height_min_cm: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    preferred_height_max_cm: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )

    # --- Marital status (array of acceptable values) ---
    preferred_marital_statuses: Mapped[list | None] = mapped_column(
        ARRAY(Enum(MaritalStatusEnum, name="marital_status_enum", create_type=False)),
        nullable=True,
    )

    # --- Disability types (soft filter) ---
    preferred_disability_types: Mapped[list | None] = mapped_column(
        ARRAY(Enum(DisabilityTypeEnum, name="disability_type_enum", create_type=False)),
        nullable=True,
    )

    # --- Education (soft filter) ---
    preferred_education: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # --- Religion (configurable hard/soft) ---
    preferred_religion: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    religion_is_strict: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="TRUE = hard filter on religion.",
    )

    # --- Caste (soft filter) ---
    preferred_caste: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Location (soft filter) ---
    preferred_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Soft — ORDER BY proximity."
    )
    preferred_state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Language (soft filter) ---
    preferred_mother_tongue: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # --- Income (soft filter) ---
    preferred_annual_income: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Range string."
    )

    # --- Relationships ---
    profile: Mapped["Profile"] = relationship(  # noqa: F821
        "Profile",
        back_populates="partner_preferences",
        lazy="noload",
    )

    # --- Constraints (Database.md §3.5) ---
    __table_args__ = (
        CheckConstraint(
            "age_min IS NULL OR age_max IS NULL OR age_min <= age_max",
            name="ck_partner_preferences_age_range",
        ),
        CheckConstraint(
            "preferred_height_min_cm IS NULL OR preferred_height_max_cm IS NULL "
            "OR preferred_height_min_cm <= preferred_height_max_cm",
            name="ck_partner_preferences_height_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<PartnerPreference id={self.id} profile_id={self.profile_id}>"
