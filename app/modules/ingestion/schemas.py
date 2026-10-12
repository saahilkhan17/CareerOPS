"""Ingestion schemas: listings, import payloads, run ledger."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ingestion.models import Listing


class ListingSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: str
    required: bool


class ListingOut(BaseModel):
    id: uuid.UUID
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    description: str | None
    url: str | None
    posted_at: datetime | None
    created_at: datetime
    skills: list[ListingSkillOut] = Field(default_factory=list)
    match_score: int | None = None


class PaginatedListings(BaseModel):
    items: list[ListingOut]
    total: int
    limit: int
    offset: int


class ImportRecord(BaseModel):
    title: str = Field(min_length=1, max_length=320)
    company: str = Field(min_length=1, max_length=320)
    location: str | None = Field(default=None, max_length=320)
    description: str | None = None
    url: str | None = Field(default=None, max_length=2000)
    posted_at: datetime | None = None


class ImportIn(BaseModel):
    format: str = Field(pattern="^(json|csv)$")
    records: list[ImportRecord] = Field(default_factory=list)
    csv_text: str | None = None


class ImportOut(BaseModel):
    fetched: int
    inserted: int
    skipped: int
    errors: int


class IngestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    started_at: datetime
    finished_at: datetime | None
    fetched: int
    inserted: int
    skipped: int
    errors: int
    error_detail: str | None


def listing_out(
    row: Listing,
    skills: list[ListingSkillOut],
    score: int | None,
) -> ListingOut:
    """Assemble a ListingOut from a row plus prefetched relations."""
    return ListingOut(
        id=row.id,
        source=row.source,
        external_id=row.external_id,
        title=row.title,
        company=row.company,
        location=row.location,
        remote=row.remote,
        salary_min=row.salary_min,
        salary_max=row.salary_max,
        currency=row.currency,
        description=row.description,
        url=row.url,
        posted_at=row.posted_at,
        created_at=row.created_at,
        skills=skills,
        match_score=score,
    )
