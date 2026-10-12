"""Ingestion read models: listings, skills, scores, runs. No fetch logic."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.models import IngestionRun, Listing, ListingSkill
from app.modules.match.models import MatchResult


async def list_listings(
    session: AsyncSession,
    source: str | None = None,
    company: str | None = None,
    query: str | None = None,
    remote: bool | None = None,
    min_score: int | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Listing], int]:
    """Filtered listings, newest first, plus total. min_score is caller-scoped."""
    stmt = select(Listing)
    if source is not None:
        stmt = stmt.where(Listing.source == source)
    if company:
        stmt = stmt.where(Listing.company.ilike(f"%{company}%"))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Listing.title.ilike(like),
                Listing.company.ilike(like),
                Listing.description.ilike(like),
            )
        )
    if remote is not None:
        stmt = stmt.where(Listing.remote.is_(remote))
    if min_score is not None and user_id is not None:
        stmt = stmt.where(
            select(MatchResult.id)
            .where(
                MatchResult.user_id == user_id,
                MatchResult.listing_id == Listing.id,
                MatchResult.score >= min_score,
            )
            .exists()
        )
    stmt = stmt.order_by(Listing.created_at.desc(), Listing.id.asc())
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.execute(stmt.limit(limit).offset(offset))
    return list(rows.scalars().all()), total or 0


async def get_listing(session: AsyncSession, listing_id: uuid.UUID) -> Listing | None:
    return await session.get(Listing, listing_id)


async def skills_for(
    session: AsyncSession, listing_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ListingSkill]]:
    """Batch-fetch skills for a page of listings (no N+1)."""
    if not listing_ids:
        return {}
    result = await session.execute(
        select(ListingSkill)
        .where(ListingSkill.listing_id.in_(listing_ids))
        .order_by(ListingSkill.skill.asc())
    )
    grouped: dict[uuid.UUID, list[ListingSkill]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.listing_id, []).append(row)
    return grouped


async def latest_scores(
    session: AsyncSession, user_id: uuid.UUID, listing_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Caller's best score per listing, one query (no N+1)."""
    if not listing_ids:
        return {}
    result = await session.execute(
        select(Listing.id, func.max(MatchResult.score))
        .outerjoin(
            MatchResult,
            (MatchResult.listing_id == Listing.id) & (MatchResult.user_id == user_id),
        )
        .where(Listing.id.in_(listing_ids))
        .group_by(Listing.id)
    )
    return {listing_id: score for listing_id, score in result.all() if score is not None}


async def list_runs(
    session: AsyncSession, source: str | None = None, limit: int = 20
) -> list[IngestionRun]:
    """Ingestion ledger, newest first."""
    stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc(), IngestionRun.id.asc())
    if source is not None:
        stmt = stmt.where(IngestionRun.source == source)
    result = await session.execute(stmt.limit(limit))
    return list(result.scalars().all())
