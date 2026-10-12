"""Profile + match results tables (Phase 3).

Revision ID: 0003_match
Revises: 0002_auth_tracker
Create Date: 2026-10-12

Hand-written against the PG dialect (no live DB on this machine for
autogenerate). Mirrors app/modules/match/models.py.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_match"
down_revision: str | None = "0002_auth_tracker"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("education", sa.Text(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
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
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], unique=True)

    op.create_table(
        "match_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(320), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_match_results_user_id", "match_results", ["user_id"])
    op.create_index("ix_match_results_created_at", "match_results", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_match_results_created_at", table_name="match_results")
    op.drop_index("ix_match_results_user_id", table_name="match_results")
    op.drop_table("match_results")
    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")
