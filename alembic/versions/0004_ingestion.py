"""Auth + tracker + match + ingestion tables (Phase 4).

Revision ID: 0004_ingestion
Revises: 0003_match
Create Date: 2026-10-12

Hand-written against the PG dialect (no live DB on this machine for
autogenerate). Mirrors app/modules/ingestion/models.py, plus an index on
match_results.listing_id for the min_score query.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_ingestion"
down_revision: str | None = "0003_match"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("external_id", sa.String(320), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("company", sa.String(320), nullable=False),
        sa.Column("location", sa.String(320), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_listings_source_external"),
    )
    op.create_index("ix_listings_source", "listings", ["source"])
    op.create_index("ix_listings_content_hash", "listings", ["content_hash"])
    op.create_index("ix_listings_created", "listings", ["created_at"])

    op.create_table(
        "listing_skills",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill", sa.String(120), primary_key=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])

    op.create_index("ix_match_results_listing_id", "match_results", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_match_results_listing_id", table_name="match_results")
    op.drop_index("ix_ingestion_runs_source", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("listing_skills")
    op.drop_index("ix_listings_created", table_name="listings")
    op.drop_index("ix_listings_content_hash", table_name="listings")
    op.drop_index("ix_listings_source", table_name="listings")
    op.drop_table("listings")
