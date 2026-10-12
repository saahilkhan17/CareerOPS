"""Analytics queries. Aggregations happen in SQL; Python only shapes results."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.time import utcnow
from app.modules.analytics.models import SkillDailyCount
from app.modules.ingestion.models import Listing, ListingSkill


def _cutoff(days: int) -> datetime | None:
    return utcnow() - timedelta(days=days) if days > 0 else None


def _listing_filters[S: Select[Any]](stmt: S, role: str | None, location: str | None) -> S:
    if role:
        stmt = stmt.where(Listing.title.ilike(f"%{role}%"))
    if location:
        stmt = stmt.where(Listing.location.ilike(f"%{location}%"))
    return stmt


async def top_skills_live(
    session: AsyncSession,
    role: str | None,
    location: str | None,
    days: int,
    limit: int,
) -> tuple[list[tuple[str, int]], int]:
    """(skill, postings) ranked + distinct-skill total, computed live in SQL."""
    cutoff = _cutoff(days)
    base = select(ListingSkill.skill).join(Listing, Listing.id == ListingSkill.listing_id)
    if cutoff is not None:
        base = base.where(Listing.created_at >= cutoff)
    base = _listing_filters(base, role, location)
    sub = base.subquery()
    rows = await session.execute(
        select(sub.c.skill, func.count().label("n"))
        .group_by(sub.c.skill)
        .order_by(func.count().desc(), sub.c.skill.asc())
        .limit(limit)
    )
    items = [(skill, int(n)) for skill, n in rows.all()]
    total = await session.scalar(select(func.count(func.distinct(sub.c.skill))))
    return items, total or 0


async def top_skills_summary(
    session: AsyncSession, days: int, limit: int
) -> tuple[list[tuple[str, int]], int]:
    """Same shape as top_skills_live but served from the precomputed table."""
    stmt = select(SkillDailyCount.skill, func.sum(SkillDailyCount.postings))
    if days > 0:
        stmt = stmt.where(SkillDailyCount.day >= (utcnow().date() - timedelta(days=days)))
    rows = await session.execute(
        stmt.group_by(SkillDailyCount.skill)
        .order_by(func.sum(SkillDailyCount.postings).desc(), SkillDailyCount.skill.asc())
        .limit(limit)
    )
    items = [(skill, int(n)) for skill, n in rows.all()]
    total = await session.scalar(select(func.count(func.distinct(SkillDailyCount.skill))))
    return items, total or 0


async def cooccurring(session: AsyncSession, skill: str, limit: int) -> list[tuple[str, int]]:
    """Skills sharing listings with `skill`, ranked by shared-listing count."""
    inner = select(ListingSkill.listing_id).where(ListingSkill.skill == skill)
    rows = await session.execute(
        select(ListingSkill.skill, func.count().label("n"))
        .where(
            ListingSkill.listing_id.in_(inner),
            ListingSkill.skill != skill,
        )
        .group_by(ListingSkill.skill)
        .order_by(func.count().desc(), ListingSkill.skill.asc())
        .limit(limit)
    )
    return [(name, int(n)) for name, n in rows.all()]


async def salary_midpoints(
    session: AsyncSession, role: str | None, location: str | None
) -> list[float]:
    """DB-sorted compensation midpoints (single query; Python only picks)."""
    midpoint = (
        func.coalesce(Listing.salary_min, Listing.salary_max)
        + func.coalesce(Listing.salary_max, Listing.salary_min)
    ) / 2.0
    stmt = select(midpoint).where(
        (Listing.salary_min.is_not(None)) | (Listing.salary_max.is_not(None))
    )
    stmt = _listing_filters(stmt, role, location)
    rows = await session.execute(stmt.order_by(midpoint.asc()))
    return [float(v) for v in rows.scalars().all()]


async def daily_postings(session: AsyncSession, days: int) -> list[tuple[str, int]]:
    """Per-day posting counts (ISO day strings), oldest first."""
    day_col = func.date(Listing.created_at)
    stmt = select(day_col, func.count())
    cutoff = _cutoff(days)
    if cutoff is not None:
        stmt = stmt.where(Listing.created_at >= cutoff)
    rows = await session.execute(stmt.group_by(day_col).order_by(day_col.asc()))
    return [(str(day)[:10], int(n)) for day, n in rows.all()]


async def rebuild_summary(session: AsyncSession) -> int:
    """Full deterministic rebuild of skill_daily_counts. Returns row count."""
    await session.execute(delete(SkillDailyCount))
    day_col = func.date(Listing.created_at)
    stmt = (
        insert(SkillDailyCount)
        .from_select(
            ["day", "skill", "postings"],
            select(day_col, ListingSkill.skill, func.count())
            .join(Listing, Listing.id == ListingSkill.listing_id)
            .group_by(day_col, ListingSkill.skill),
        )
        .returning(SkillDailyCount.day)
    )
    result = await session.execute(stmt)
    rows = result.all()
    await session.commit()
    return len(rows)
