"""Auth + tracker tables (Phase 2).

Revision ID: 0002_auth_tracker
Revises: 0001_initial
Create Date: 2026-10-12

Hand-written against the PG dialect (no live DB on this machine for
autogenerate). Mirrors app/modules/auth/models.py + tracker/models.py.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_auth_tracker"
down_revision: str | None = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None

STATUS_ENUM = postgresql.ENUM(
    "saved",
    "applied",
    "oa",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    name="application_status",
)


def upgrade() -> None:
    STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(320), nullable=False),
        sa.Column("website", sa.String(500), nullable=True),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=True)

    op.create_table(
        "job_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("location", sa.String(320), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resume_version", sa.String(120), nullable=True),
        sa.Column("status", STATUS_ENUM, nullable=False, server_default="saved"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_applications_user_status", "job_applications", ["user_id", "status"])
    op.create_index("ix_applications_user_created", "job_applications", ["user_id", "created_at"])

    op.create_table(
        "status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", STATUS_ENUM, nullable=True),
        sa.Column("to_status", STATUS_ENUM, nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_history_application", "status_history", ["application_id"])

    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notes_application_id", "notes", ["application_id"])

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reminders_application_id", "reminders", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_application_id", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("ix_notes_application_id", table_name="notes")
    op.drop_table("notes")
    op.drop_index("ix_history_application", table_name="status_history")
    op.drop_table("status_history")
    op.drop_index("ix_applications_user_created", table_name="job_applications")
    op.drop_index("ix_applications_user_status", table_name="job_applications")
    op.drop_table("job_applications")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
