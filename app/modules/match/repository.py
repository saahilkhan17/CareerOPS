"""Match persistence: profiles and match results. No scoring logic here."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.match.models import MatchResult, Profile


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_profile(
    session: AsyncSession,
    user_id: uuid.UUID,
    skills: list[dict[str, object]],
    target_roles: list[str],
    education: str | None,
    preferences: dict[str, object],
) -> Profile:
    row = await get_profile(session, user_id)
    if row is None:
        row = Profile(
            user_id=user_id,
            skills=skills,
            target_roles=target_roles,
            education=education,
            preferences=preferences,
        )
        session.add(row)
    else:
        row.skills = skills
        row.target_roles = target_roles
        row.education = education
        row.preferences = preferences
        row.updated_at = utcnow()
    await session.flush()
    return row


async def create_match_result(
    session: AsyncSession,
    user_id: uuid.UUID,
    score: int,
    breakdown: dict[str, object],
    title: str | None = None,
    application_id: uuid.UUID | None = None,
) -> MatchResult:
    row = MatchResult(
        user_id=user_id,
        application_id=application_id,
        title=title,
        score=score,
        breakdown=breakdown,
    )
    session.add(row)
    await session.flush()
    return row


async def list_match_results(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[MatchResult]:
    result = await session.execute(
        select(MatchResult)
        .where(MatchResult.user_id == user_id)
        .order_by(MatchResult.created_at.desc(), MatchResult.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
