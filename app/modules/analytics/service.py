"""Analytics shaping: bucketing, gap analysis, order statistics, refresh."""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.cache import invalidate_analytics
from app.modules.analytics import repository
from app.modules.match import repository as match_repository
from app.modules.match.scorer import profile_view


def salary_stats(values: list[float], min_n: int) -> dict[str, int | None]:
    """Order statistics over DB-sorted midpoints (pure picking, no loops)."""
    count = len(values)
    if count < min_n or count == 0:
        return {"count": count, "min": None, "median": None, "p75": None}
    ordered = sorted(values)
    median = ordered[count // 2]
    p75 = ordered[min(int(count * 0.75), count - 1)]
    return {
        "count": count,
        "min": int(round(ordered[0])),
        "median": int(round(median)),
        "p75": int(round(p75)),
    }


def bucket_trends(daily: list[tuple[str, int]], granularity: str) -> list[dict[str, object]]:
    """Bucket per-day counts into day/week/month series, zero-filled."""
    buckets: dict[str, int] = {}
    for day_str, count in daily:
        day = date.fromisoformat(day_str)
        if granularity == "month":
            key = day.strftime("%Y-%m-01")
        elif granularity == "week":
            monday = day - timedelta(days=day.weekday())
            key = monday.isoformat()
        else:
            key = day.isoformat()
        buckets[key] = buckets.get(key, 0) + count
    if not buckets:
        return []
    if granularity == "month":
        return _month_series(buckets)
    step = 1 if granularity == "day" else 7
    points: list[dict[str, object]] = []
    cursor = date.fromisoformat(min(buckets))
    end_date = date.fromisoformat(max(buckets))
    while cursor <= end_date:
        key = cursor.isoformat()
        points.append({"bucket": key, "postings": buckets.get(key, 0)})
        cursor += timedelta(days=step)
    return points


def _month_series(buckets: dict[str, int]) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    cursor = date.fromisoformat(min(buckets))
    end_date = date.fromisoformat(max(buckets))
    while cursor <= end_date:
        key = cursor.strftime("%Y-%m-01")
        points.append({"bucket": key, "postings": buckets.get(key, 0)})
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return points


async def my_gap(
    session: AsyncSession, user_id: uuid.UUID, role: str | None, location: str | None
) -> list[dict[str, object]]:
    """Top in-demand skills the user's profile lacks (demand-descending)."""
    items, _ = await repository.top_skills_live(session, role, location, days=30, limit=50)
    profile = await match_repository.get_profile(session, user_id)
    if profile is None:
        return [{"skill": skill, "postings": postings} for skill, postings in items]
    have = set(profile_view(profile.skills, profile.target_roles).skills)
    return [
        {"skill": skill, "postings": postings} for skill, postings in items if skill not in have
    ]


async def refresh_summary(factory: async_sessionmaker[AsyncSession]) -> int:
    """Rebuild the skill summary table + drop cached analytics."""
    async with factory() as session:
        count = await repository.rebuild_summary(session)
    await invalidate_analytics()
    return count
