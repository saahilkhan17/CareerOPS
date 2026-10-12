"""Skill summary table (Phase 5).

Revision ID: 0005_analytics
Revises: 0004_ingestion
Create Date: 2026-10-12

Hand-written against the PG dialect (no live DB on this machine for
autogenerate). Mirrors app/modules/analytics/models.py.
(Audit log table ships separately in 0006_audit.)
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0005_analytics"
down_revision: str | None = "0004_ingestion"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "skill_daily_counts",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("skill", sa.String(120), nullable=False),
        sa.Column("postings", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "skill"),
    )


def downgrade() -> None:
    op.drop_table("skill_daily_counts")
