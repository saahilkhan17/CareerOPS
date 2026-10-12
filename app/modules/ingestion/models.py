"""Ingestion ORM models: listings, listing skills, ingestion runs."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base


class Listing(Base):
    """One normalized job listing from a legitimate public source."""

    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_listings_source_external"),
        Index("ix_listings_source", "source"),
        Index("ix_listings_content_hash", "content_hash"),
        Index("ix_listings_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(60))
    external_id: Mapped[str] = mapped_column(String(320))
    title: Mapped[str] = mapped_column(String(320))
    company: Mapped[str] = mapped_column(String(320))
    location: Mapped[str | None] = mapped_column(String(320), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )

    skills: Mapped[list["ListingSkill"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class ListingSkill(Base):
    """Canonical skill tagged on a listing (required vs preferred signal)."""

    __tablename__ = "listing_skills"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    skill: Mapped[str] = mapped_column(String(120), primary_key=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class IngestionRun(Base):
    """Operational ledger row for one ingestion run of one source."""

    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(60), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
