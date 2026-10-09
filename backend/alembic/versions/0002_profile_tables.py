"""
0002 — Profile module tables.

Creates:
- profiles
- sensitive_profile_data
- partner_preferences
- sensitive_data_access_logs
- platform_config

And the profile-domain PostgreSQL enum types.

See Database.md §3.2, §3.3, §3.5, §3.15, §3.20.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "0002"
down_revision = "0001_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1. Create PostgreSQL enum types
    # -------------------------------------------------------------------
    op.execute("CREATE TYPE gender_enum AS ENUM ('MALE', 'FEMALE', 'OTHER')")
    op.execute("CREATE TYPE profile_managed_by_enum AS ENUM ('SELF', 'PARENT', 'SIBLING', 'GUARDIAN')")
    op.execute("CREATE TYPE disability_type_enum AS ENUM ('PHYSICAL', 'VISUAL', 'HEARING', 'INTELLECTUAL', 'MULTIPLE')")
    op.execute("CREATE TYPE marital_status_enum AS ENUM ('NEVER_MARRIED', 'DIVORCED', 'WIDOWED', 'SEPARATED')")
    op.execute("CREATE TYPE verification_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")

    # -------------------------------------------------------------------
    # 2. platform_config (must exist before profiles, for logical refs)
    # -------------------------------------------------------------------
    op.create_table(
        "platform_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_key", sa.String(50), nullable=False, unique=True),
        sa.Column("app_name", sa.String(100), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "settings ? 'minimum_age' AND settings ? 'maximum_age' "
            "AND settings ? 'require_disability'",
            name="ck_platform_config_required_settings",
        ),
    )

    # Seed Divyang Matrimony platform config
    op.execute(
        """
        INSERT INTO platform_config (id, platform_key, app_name, settings)
        VALUES (
            gen_random_uuid(),
            'divyang_matrimony',
            'Divyang Matrimony',
            '{"minimum_age": 18, "maximum_age": 80, "require_disability": true,
              "primary_color": "#1A73E8"}'::jsonb
        )
        ON CONFLICT (platform_key) DO NOTHING
        """
    )

    # -------------------------------------------------------------------
    # 3. profiles
    # -------------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "platform_id",
            sa.String(50),
            nullable=False,
            server_default="divyang_matrimony",
        ),
        sa.Column(
            "managed_by",
            postgresql.ENUM('SELF', 'PARENT', 'SIBLING', 'GUARDIAN', name='profile_managed_by_enum', create_type=False),
            nullable=False,
            server_default="SELF",
        ),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("gender", postgresql.ENUM('MALE', 'FEMALE', 'OTHER', name='gender_enum', create_type=False), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("marital_status", postgresql.ENUM('NEVER_MARRIED', 'DIVORCED', 'WIDOWED', 'SEPARATED', name='marital_status_enum', create_type=False), nullable=False),
        sa.Column("height_cm", sa.SmallInteger, nullable=True),
        sa.Column("education", sa.String(200), nullable=True),
        sa.Column("occupation", sa.String(200), nullable=True),
        sa.Column("annual_income", sa.String(100), nullable=True),
        sa.Column("mother_tongue", sa.String(50), nullable=True),
        sa.Column("languages_spoken", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column(
            "country", sa.String(50), nullable=False, server_default="India"
        ),
        sa.Column("pincode", sa.String(10), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("disability_type", postgresql.ENUM('PHYSICAL', 'VISUAL', 'HEARING', 'INTELLECTUAL', 'MULTIPLE', name='disability_type_enum', create_type=False), nullable=True),
        sa.Column(
            "completeness_score",
            sa.SmallInteger,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_profile_visible",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "verification_status",
            postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='verification_status_enum', create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 100",
            name="ck_profiles_completeness_score_range",
        ),
    )

    # Indexes on profiles
    op.create_index(
        "ix_profiles_platform_id", "profiles", ["platform_id"]
    )
    op.create_index(
        "ix_profiles_search_vector",
        "profiles",
        ["search_vector"],
        postgresql_using="gin",
    )

    # -------------------------------------------------------------------
    # 4. sensitive_profile_data
    # -------------------------------------------------------------------
    op.create_table(
        "sensitive_profile_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("disability_percentage", sa.SmallInteger, nullable=True),
        sa.Column("disability_details", sa.Text, nullable=True),
        sa.Column("disability_since", sa.String(50), nullable=True),
        sa.Column("mobility_aid", sa.String(200), nullable=True),
        sa.Column("health_conditions", sa.Text, nullable=True),
        sa.Column("religion", sa.String(100), nullable=True),
        sa.Column("caste", sa.String(100), nullable=True),
        sa.Column("sub_caste", sa.String(100), nullable=True),
        sa.Column("family_type", sa.String(50), nullable=True),
        sa.Column("family_status", sa.String(50), nullable=True),
        sa.Column("father_occupation", sa.String(200), nullable=True),
        sa.Column("mother_occupation", sa.String(200), nullable=True),
        sa.Column("siblings", sa.String(200), nullable=True),
        sa.Column("about_family", sa.Text, nullable=True),
        sa.Column("contact_phone", sa.Text, nullable=True),
        sa.Column("contact_email", sa.Text, nullable=True),
        sa.Column("whatsapp_number", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "disability_percentage IS NULL OR "
            "(disability_percentage >= 0 AND disability_percentage <= 100)",
            name="ck_sensitive_profile_data_disability_pct_range",
        ),
    )

    # -------------------------------------------------------------------
    # 5. partner_preferences
    # -------------------------------------------------------------------
    op.create_table(
        "partner_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("preferred_gender", postgresql.ENUM('MALE', 'FEMALE', 'OTHER', name='gender_enum', create_type=False), nullable=True),
        sa.Column("age_min", sa.SmallInteger, nullable=True),
        sa.Column("age_max", sa.SmallInteger, nullable=True),
        sa.Column("preferred_height_min_cm", sa.SmallInteger, nullable=True),
        sa.Column("preferred_height_max_cm", sa.SmallInteger, nullable=True),
        sa.Column(
            "preferred_marital_statuses",
            postgresql.ARRAY(postgresql.ENUM('NEVER_MARRIED', 'DIVORCED', 'WIDOWED', 'SEPARATED', name='marital_status_enum', create_type=False)),
            nullable=True,
        ),
        sa.Column(
            "preferred_disability_types",
            postgresql.ARRAY(postgresql.ENUM('PHYSICAL', 'VISUAL', 'HEARING', 'INTELLECTUAL', 'MULTIPLE', name='disability_type_enum', create_type=False)),
            nullable=True,
        ),
        sa.Column("preferred_education", sa.String(200), nullable=True),
        sa.Column("preferred_religion", sa.String(100), nullable=True),
        sa.Column(
            "religion_is_strict",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("preferred_caste", sa.String(100), nullable=True),
        sa.Column("preferred_city", sa.String(100), nullable=True),
        sa.Column("preferred_state", sa.String(100), nullable=True),
        sa.Column("preferred_mother_tongue", sa.String(50), nullable=True),
        sa.Column("preferred_annual_income", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "age_min IS NULL OR age_max IS NULL OR age_min <= age_max",
            name="ck_partner_preferences_age_range",
        ),
        sa.CheckConstraint(
            "preferred_height_min_cm IS NULL OR preferred_height_max_cm IS NULL "
            "OR preferred_height_min_cm <= preferred_height_max_cm",
            name="ck_partner_preferences_height_range",
        ),
    )

    # -------------------------------------------------------------------
    # 6. sensitive_data_access_logs
    # -------------------------------------------------------------------
    op.create_table(
        "sensitive_data_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "accessor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "target_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id"),
            nullable=False,
        ),
        sa.Column(
            "fields_accessed",
            postgresql.ARRAY(sa.Text),
            nullable=False,
        ),
        sa.Column("access_tier", sa.String(20), nullable=False),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column(
            "platform_id",
            sa.String(50),
            nullable=False,
            server_default="divyang_matrimony",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_sensitive_data_access_logs_accessor_created",
        "sensitive_data_access_logs",
        ["accessor_user_id", "created_at"],
    )
    op.create_index(
        "ix_sensitive_data_access_logs_target_created",
        "sensitive_data_access_logs",
        ["target_profile_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("sensitive_data_access_logs")
    op.drop_table("partner_preferences")
    op.drop_table("sensitive_profile_data")
    op.drop_table("profiles")
    op.drop_table("platform_config")

    # Drop enum types (in reverse dependency order)
    op.execute("DROP TYPE IF EXISTS verification_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS marital_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS disability_type_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS profile_managed_by_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS gender_enum CASCADE")
