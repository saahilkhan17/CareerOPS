"""Match routes: profile CRUD, paste-JD and application scoring, history."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.db.session import get_session
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.match import repository, service
from app.modules.match.models import MatchResult
from app.modules.match.schemas import (
    MatchHistoryOut,
    MatchRequest,
    MatchResponse,
    ProfileIn,
    ProfileOut,
)
from app.modules.match.scorer import MatchScore
from app.modules.match.taxonomy import TAXONOMY_VERSION

router = APIRouter(tags=["match"])


def _to_response(row: MatchResult, scored: MatchScore, llm: str | None) -> MatchResponse:
    return MatchResponse(
        id=row.id,
        score=scored.score,
        breakdown=scored.breakdown,
        matched_skills=scored.matched_skills,
        missing_skills=scored.missing_skills,
        suggestions=scored.suggestions,
        llm_explanation=llm,
        created_at=row.created_at,
    )


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    """Fetch my profile (404 when never created)."""
    profile = await repository.get_profile(session, user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return ProfileOut.model_validate(service.profile_out(profile))


@router.put("/profile", response_model=ProfileOut)
async def put_profile(
    payload: ProfileIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileOut:
    """Create or replace my profile (skills stored raw, canonicalized at score)."""
    profile = await service.upsert_profile(
        session,
        user,
        [s.model_dump() for s in payload.skills],
        payload.target_roles,
        payload.education,
        payload.preferences,
    )
    await cache.invalidate_user_gap(str(user.id))
    return ProfileOut.model_validate(service.profile_out(profile))


@router.post("/match", response_model=MatchResponse)
async def match_pasted(
    payload: MatchRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MatchResponse:
    """Score pasted JD text against my profile and persist the result."""
    try:
        row, scored = await service.run_match(session, user, payload.title, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    llm = await service.explain_result(payload.title, scored)
    return _to_response(row, scored, llm)


@router.post("/match/{application_id}", response_model=MatchResponse)
async def match_application(
    application_id: uuid.UUID,
    payload: MatchRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MatchResponse:
    """Score JD text in the context of one of my applications."""
    from app.modules.tracker import service as tracker_service

    try:
        app_row = await tracker_service.get_owned(session, user, application_id)
    except tracker_service.NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="application not found"
        ) from None
    title = payload.title or app_row.title
    try:
        row, scored = await service.run_match(
            session, user, title, payload.text, application_id=application_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    llm = await service.explain_result(title, scored)
    return _to_response(row, scored, llm)


@router.get("/match/history", response_model=list[MatchHistoryOut])
async def match_history(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MatchHistoryOut]:
    """My persisted match results, newest first."""
    rows = await repository.list_match_results(session, user.id, limit, offset)
    return [MatchHistoryOut.model_validate(r) for r in rows]


@router.get("/match/taxonomy-version")
async def taxonomy_version() -> dict[str, str]:
    """Expose the taxonomy version (useful for debugging P/R drift)."""
    return {"version": TAXONOMY_VERSION}
