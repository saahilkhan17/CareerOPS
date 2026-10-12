"""Match orchestration: extract → score → persist (+ optional explanation)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit import repository as audit_repository
from app.modules.auth.models import User
from app.modules.match import explainer as explainer_module
from app.modules.match import repository, scorer
from app.modules.match.extractor import extract
from app.modules.match.models import MatchResult, Profile


def weights_from_settings() -> scorer.Weights:
    """Read scoring weights from config (tests may pass Weights directly)."""
    settings = get_settings()
    return scorer.Weights(
        required=settings.match_weight_required,
        preferred=settings.match_weight_preferred,
        experience=settings.match_weight_experience,
        title=settings.match_weight_title,
    )


def llm_enabled() -> bool:
    """Feature flag for the optional LLM explanation (default off)."""
    return get_settings().match_llm_enabled


async def upsert_profile(
    session: AsyncSession,
    user: User,
    skills: list[dict[str, object]],
    target_roles: list[str],
    education: str | None,
    preferences: dict[str, object],
) -> Profile:
    """Create/replace the profile and audit the change (single commit)."""
    profile = await repository.upsert_profile(
        session, user.id, skills, target_roles, education, preferences
    )
    await audit_repository.log(session, user.id, "match.profile.upsert", "profile", profile.id)
    await session.commit()
    await session.refresh(profile)
    return profile


async def run_match(
    session: AsyncSession,
    user: User,
    title: str | None,
    text: str,
    application_id: uuid.UUID | None = None,
) -> tuple[MatchResult, scorer.MatchScore]:
    """Score pasted JD text and persist the result. Raises ValueError on blank."""
    extracted = extract(text)
    profile = await repository.get_profile(session, user.id)
    view = scorer.profile_view(
        profile.skills if profile else [],
        profile.target_roles if profile else [],
    )
    scored = scorer.score_match(view, extracted, title, weights_from_settings())
    row = await repository.create_match_result(
        session,
        user.id,
        scored.score,
        scored.breakdown,
        title=title,
        application_id=application_id,
    )
    await session.commit()
    await session.refresh(row)
    return row, scored


async def explain_result(title: str | None, scored: scorer.MatchScore) -> str | None:
    """Return an LLM explanation only when flag + explainer are both present."""
    if not llm_enabled():
        return None
    expl = explainer_module.get_explainer()
    if expl is None:
        return None
    return expl.explain(
        title=title,
        score=scored.score,
        breakdown=scored.breakdown,
        missing_skills=scored.missing_skills,
    )


def profile_out(profile: Profile) -> dict[str, object]:
    """Serialize a profile row for ProfileOut (skills pass through raw)."""
    return {
        "skills": profile.skills,
        "target_roles": profile.target_roles,
        "education": profile.education,
        "preferences": profile.preferences,
        "updated_at": profile.updated_at,
    }
