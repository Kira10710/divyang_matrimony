"""
Initial auth tables migration.

Creates:
  - admin_role_enum
  - login_event_type_enum
  - users (with soft-delete)
  - active_sessions
  - login_history

Partial unique indexes are created as raw SQL (SQLAlchemy UniqueConstraint
cannot express WHERE clauses, so they are handled here manually).

See Database.md §3.1, §3.16, §3.18, §4.2.
Architecture §12: migrations run as a separate deploy step, never on boot.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# Alembic migration metadata
revision: str = "0001_auth_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Enum types (must exist before tables that reference them)
    # -----------------------------------------------------------------------

    op.execute("CREATE TYPE admin_role_enum AS ENUM ('SUPER_ADMIN', 'ADMIN', 'SUPPORT')")
    op.execute("CREATE TYPE login_event_type_enum AS ENUM ('LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'TOKEN_REFRESH')")

    # -----------------------------------------------------------------------
    # users table (Database.md §3.1)
    # -----------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "platform_id",
            sa.String(50),
            nullable=False,
            server_default="divyang_matrimony",
        ),
        sa.Column("phone", sa.String(15), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("SUPER_ADMIN", "ADMIN", "SUPPORT", name="admin_role_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "is_banned", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_phone_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_email_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("fcm_token", sa.String(255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Partial unique indexes (WHERE deleted_at IS NULL)
    # Cannot be expressed in SQLAlchemy's UniqueConstraint — raw SQL required.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_users_phone_platform_active
        ON users (phone, platform_id)
        WHERE deleted_at IS NULL AND phone IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_users_email_platform_active
        ON users (email, platform_id)
        WHERE deleted_at IS NULL AND email IS NOT NULL
        """
    )

    # Regular index for purge job (WHERE deleted_at IS NOT NULL)
    op.create_index(
        "ix_users_deleted_at",
        "users",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # -----------------------------------------------------------------------
    # active_sessions table (Database.md §3.18)
    # -----------------------------------------------------------------------
    op.create_table(
        "active_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_jti", sa.String(100), nullable=False, unique=True),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            server_default=sa.text("now()"),
        ),
        # Constraint: revoked_at only set when is_revoked = TRUE
        sa.CheckConstraint(
            "revoked_at IS NULL OR is_revoked = TRUE",
            name="ck_active_sessions_revoked_at_consistency",
        ),
    )
    op.create_index(
        "ix_active_sessions_user_id_is_revoked",
        "active_sessions",
        ["user_id", "is_revoked"],
    )
    op.create_index(
        "ix_active_sessions_expires_at",
        "active_sessions",
        ["expires_at"],
    )

    # -----------------------------------------------------------------------
    # login_history table (Database.md §3.16)
    # -----------------------------------------------------------------------
    op.create_table(
        "login_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "LOGIN_SUCCESS",
                "LOGIN_FAILED",
                "LOGOUT",
                "TOKEN_REFRESH",
                name="login_event_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("refresh_token_jti", sa.String(100), nullable=True),
        sa.Column(
            "is_suspicious",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_login_history_user_id_created_at",
        "login_history",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("login_history")
    op.drop_table("active_sessions")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS login_event_type_enum")
    op.execute("DROP TYPE IF EXISTS admin_role_enum")
