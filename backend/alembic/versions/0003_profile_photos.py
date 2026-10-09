"""
0003 — profile_photos table.

Creates:
- moderation_status_enum  PostgreSQL enum type
- profile_photos          table with all three variant path columns,
                          display_order, is_primary, moderation state
- Partial unique index    (profile_id) WHERE is_primary = TRUE AND
                          moderation_status != 'REJECTED'
- Composite index         (moderation_status, created_at) for admin queue
- Index                   (profile_id, display_order)

See Database.md §3.4, Architecture §4.2.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. PostgreSQL enum type for moderation status
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE moderation_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")

    # ------------------------------------------------------------------
    # 2. profile_photos table  (Database.md §3.4)
    # ------------------------------------------------------------------
    op.create_table(
        "profile_photos",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # --- Firebase Storage object paths (never download URLs) ---
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("medium_path", sa.String(500), nullable=False),
        sa.Column("thumbnail_path", sa.String(500), nullable=False),
        # --- Ordering ---
        sa.Column(
            "display_order",
            sa.SmallInteger,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_primary",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        # --- Moderation ---
        sa.Column(
            "moderation_status",
            postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='moderation_status_enum', create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        # --- Timestamps (created_at only — no updated_at, photos immutable) ---
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------------------------
    # 3. Indexes (Database.md §8)
    # ------------------------------------------------------------------

    # Partial unique: only one APPROVED primary photo per profile.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_profile_photos_primary
        ON profile_photos (profile_id)
        WHERE is_primary = TRUE AND moderation_status != 'REJECTED'
        """
    )

    # Admin moderation queue (order by created_at to process oldest first).
    op.create_index(
        "ix_profile_photos_moderation_queue",
        "profile_photos",
        ["moderation_status", "created_at"],
    )

    # Photo ordering per profile.
    op.create_index(
        "ix_profile_photos_display_order",
        "profile_photos",
        ["profile_id", "display_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_profile_photos_display_order", table_name="profile_photos")
    op.drop_index("ix_profile_photos_moderation_queue", table_name="profile_photos")
    op.execute("DROP INDEX IF EXISTS uq_profile_photos_primary")
    op.drop_table("profile_photos")

    # Drop the enum type last (cannot drop while table columns reference it).
    op.execute("DROP TYPE IF EXISTS moderation_status_enum CASCADE")
