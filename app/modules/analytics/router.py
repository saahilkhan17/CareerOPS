"""Analytics routes: SQL-driven market stats + personal gap (auth required)."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.cache import cache_key
from app.core.config import get_settings
from app.db.session import get_session
from app.modules.analytics import repository, service
from app.modules.analytics.schemas import (
    CoocOut,
    GapsOut,
    SalaryOut,
    SkillsTopOut,
    TrendsOut,
)
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.match.taxonomy import canonicalize

router = APIRouter(tags=["analytics"])


def _ttl() -> int:
    return get_settings().analytics_cache_ttl


async def _cached_or_compute[T](key: str, compute: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Return the cached value or compute + store it (factory avoids dead coroutines)."""
    hit = await cache.cache_get(key)
    if hit is not None:
        return cast(T, hit)
    data = await compute()
    await cache.cache_set(key, data, _ttl())
    return data


@router.get("/analytics/skills/top", response_model=SkillsTopOut)
async def skills_top(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    role: str | None = None,
    location: str | None = None,
    days: Annotated[int, Query(ge=0, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    """Top skills by posting count. Unfiltered reads serve the summary table."""
    key = cache_key("skills-top", f"role={role}", f"loc={location}", f"d={days}", f"n={limit}")

    async def _compute() -> dict[str, object]:
        if role is None and location is None:
            items, total = await repository.top_skills_summary(session, days, limit)
        else:
            items, total = await repository.top_skills_live(session, role, location, days, limit)
        return {
            "items": [{"skill": s, "postings": n} for s, n in items],
            "total_skills": total,
        }

    return await _cached_or_compute(key, _compute)


@router.get("/analytics/skills/cooccurrence", response_model=CoocOut)
async def cooccurrence(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skill: str,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, object]:
    """Skills most often posted alongside `skill`."""
    canonical = canonicalize(skill)
    if canonical is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown skill")
    key = cache_key("cooc", canonical, f"n={limit}")

    async def _compute() -> dict[str, object]:
        rows = await repository.cooccurring(session, canonical, limit)
        return {"items": [{"skill": s, "postings": n} for s, n in rows]}

    return await _cached_or_compute(key, _compute)


@router.get("/analytics/salary", response_model=SalaryOut)
async def salary(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    role: str | None = None,
    location: str | None = None,
    min_n: Annotated[int, Query(ge=1, le=1000)] = 5,
) -> dict[str, object]:
    """Compensation stats over salary midpoints (USD assumed, documented)."""
    key = cache_key("salary", f"role={role}", f"loc={location}", f"min={min_n}")

    async def _compute() -> dict[str, object]:
        values = await repository.salary_midpoints(session, role, location)
        return {"stats": service.salary_stats(values, min_n)}

    return await _cached_or_compute(key, _compute)


@router.get("/analytics/trends", response_model=TrendsOut)
async def trends(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    granularity: Literal["day", "week", "month"] = "week",
    days: Annotated[int, Query(ge=1, le=730)] = 90,
) -> dict[str, object]:
    """Posting volume over time, bucketed and zero-filled."""
    key = cache_key("trends", granularity, f"d={days}")

    async def _compute() -> dict[str, object]:
        daily = await repository.daily_postings(session, days)
        return {
            "granularity": granularity,
            "points": service.bucket_trends(daily, granularity),
        }

    return await _cached_or_compute(key, _compute)


@router.get("/analytics/my-gap", response_model=GapsOut)
async def my_gap(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    role: str | None = None,
    location: str | None = None,
) -> dict[str, object]:
    """In-demand skills missing from my profile, demand-descending."""
    key = cache_key("gap", str(user.id), f"role={role}", f"loc={location}")

    async def _compute() -> dict[str, object]:
        return {"items": await service.my_gap(session, user.id, role, location)}

    return await _cached_or_compute(key, _compute)
