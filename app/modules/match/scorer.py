"""Deterministic JD match scorer (pure function, no I/O, no LLM).

score = round(100 * Σ(weight_i * component_i) / Σweights)

Components: required-skill coverage, preferred-skill coverage, experience fit,
title similarity. Missing data is neutral, never punishing, except an absent
skill set against stated requirements.
"""

import re
from dataclasses import dataclass, field

from app.modules.match.extractor import ExtractedJD
from app.modules.match.taxonomy import canonicalize

TITLE_STOPWORDS = frozenset(
    {
        "senior",
        "sr",
        "junior",
        "jr",
        "lead",
        "staff",
        "principal",
        "i",
        "ii",
        "iii",
        "iv",
        "v",
        "remote",
        "hybrid",
        "onsite",
        "on-site",
        "full-time",
        "fulltime",
        "contract",
        "part-time",
    }
)

MAX_SUGGESTIONS = 6


@dataclass(frozen=True)
class Weights:
    required: float = 0.5
    preferred: float = 0.2
    experience: float = 0.2
    title: float = 0.1


@dataclass
class ProfileView:
    """Scorer input: canonical skill → years, plus target role titles."""

    skills: dict[str, float] = field(default_factory=dict)
    target_roles: list[str] = field(default_factory=list)


def profile_view(raw_skills: list[dict[str, object]], roles: list[str]) -> ProfileView:
    """Normalize raw profile skills (aliases → canonical, max years kept)."""
    skills: dict[str, float] = {}
    for entry in raw_skills:
        canonical = canonicalize(str(entry.get("name", "")))
        if canonical is None:
            continue
        years = entry.get("years")
        years_f = float(years) if isinstance(years, (int, float)) else 0.0
        skills[canonical] = max(skills.get(canonical, 0.0), years_f)
    return ProfileView(skills=skills, target_roles=list(roles))


def _coverage(wanted: list[str], have: set[str]) -> tuple[float, list[str], list[str]]:
    if not wanted:
        return 1.0, [], []
    matched = [s for s in wanted if s in have]
    missing = [s for s in wanted if s not in have]
    return len(matched) / len(wanted), matched, missing


def _title_tokens(title: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9+#.]+", title.lower()))
    return {w for w in words if w not in TITLE_STOPWORDS}


def title_similarity(jd_title: str | None, target_roles: list[str]) -> tuple[float, str | None]:
    """Overlap coefficient vs the best-matching target role (0.5 when unknown)."""
    if not jd_title or not jd_title.strip() or not target_roles:
        return 0.5, None
    jd_tokens = _title_tokens(jd_title)
    if not jd_tokens:
        return 0.5, None
    best_score, best_role = 0.0, None
    for role in target_roles:
        role_tokens = _title_tokens(role)
        if not role_tokens:
            continue
        overlap = len(jd_tokens & role_tokens) / min(len(jd_tokens), len(role_tokens))
        if overlap > best_score:
            best_score, best_role = overlap, role
    return best_score, best_role


def _suggestions(
    missing_required: list[str],
    missing_preferred: list[str],
    profile_years: float,
    min_years: int | None,
    title_score: float,
    jd_title: str | None,
) -> list[str]:
    out: list[str] = []
    for skill in missing_required[:3]:
        out.append(f"Add {skill} to your resume or profile — it is required.")
    for skill in missing_preferred[:2]:
        out.append(f"Learning {skill} would strengthen this application.")
    if min_years is not None and profile_years < min_years:
        out.append(
            f"Requires {min_years}y — highlight transferable experience "
            f"(profile shows {profile_years:g}y)."
        )
    if jd_title and title_score < 0.5:
        out.append(f"Target roles don't overlap '{jd_title}' — tailor your headline.")
    return out[:MAX_SUGGESTIONS]


@dataclass
class MatchScore:
    score: int
    breakdown: dict[str, object]
    matched_skills: list[str]
    missing_skills: list[str]
    suggestions: list[str]


def score_match(
    profile: ProfileView,
    extracted: ExtractedJD,
    jd_title: str | None,
    weights: Weights,
) -> MatchScore:
    """Score an extracted JD against a profile (deterministic)."""
    have = set(profile.skills)
    req_score, req_matched, req_missing = _coverage(extracted.required, have)
    pref_score, pref_matched, pref_missing = _coverage(extracted.preferred, have)

    profile_years = max(profile.skills.values(), default=0.0)
    if extracted.min_years is None or extracted.min_years <= 0:
        exp_score = 1.0
    else:
        exp_score = min(profile_years / extracted.min_years, 1.0)

    title_score, matched_role = title_similarity(jd_title, profile.target_roles)

    total_weight = weights.required + weights.preferred + weights.experience + weights.title
    if total_weight <= 0:
        total_weight = 1.0
    blended = (
        weights.required * req_score
        + weights.preferred * pref_score
        + weights.experience * exp_score
        + weights.title * title_score
    ) / total_weight
    score = max(0, min(100, round(blended * 100)))

    matched = req_matched + [s for s in pref_matched if s not in req_matched]
    missing = req_missing + [s for s in pref_missing if s not in req_missing]
    breakdown: dict[str, object] = {
        "required": {
            "score": round(req_score * 100),
            "weight": weights.required,
            "matched": req_matched,
            "missing": req_missing,
        },
        "preferred": {
            "score": round(pref_score * 100),
            "weight": weights.preferred,
            "matched": pref_matched,
            "missing": pref_missing,
        },
        "experience": {
            "score": round(exp_score * 100),
            "weight": weights.experience,
            "profile_years": profile_years,
            "required_years": extracted.min_years,
        },
        "title": {
            "score": round(title_score * 100),
            "weight": weights.title,
            "jd_title": jd_title,
            "matched_role": matched_role,
        },
    }
    return MatchScore(
        score=score,
        breakdown=breakdown,
        matched_skills=matched,
        missing_skills=missing,
        suggestions=_suggestions(
            req_missing,
            pref_missing,
            profile_years,
            extracted.min_years,
            title_score,
            jd_title,
        ),
    )
