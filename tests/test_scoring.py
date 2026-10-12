"""Pure scorer unit tests (no DB, no app)."""

import pytest

from app.modules.match.extractor import ExtractedJD, Seniority
from app.modules.match.scorer import (
    ProfileView,
    Weights,
    profile_view,
    score_match,
    title_similarity,
)


def _extracted(**over: object) -> ExtractedJD:
    base: dict[str, object] = {
        "skills": [],
        "required": [],
        "preferred": [],
        "min_years": None,
        "seniority": Seniority(level="unspecified"),
    }
    base.update(over)
    return ExtractedJD(**base)  # type: ignore[arg-type]


def test_perfect_match_scores_100() -> None:
    profile = ProfileView(
        skills={"Python": 5.0, "FastAPI": 3.0, "PostgreSQL": 4.0},
        target_roles=["Backend Engineer"],
    )
    jd = _extracted(
        skills=["Python", "FastAPI", "PostgreSQL"],
        required=["Python", "FastAPI"],
        preferred=["PostgreSQL"],
        min_years=3,
    )
    out = score_match(profile, jd, "Backend Engineer", Weights())
    assert out.score == 100
    assert out.missing_skills == []
    assert set(out.matched_skills) == {"Python", "FastAPI", "PostgreSQL"}


def test_empty_everything_scores_95() -> None:
    # required 1.0 + preferred 1.0 + experience 1.0 + title 0.5 (neutral),
    # weighted (0.5+0.2+0.2+0.05) = 0.95.
    out = score_match(ProfileView(), _extracted(), None, Weights())
    assert out.score == 95


def test_no_overlap_scores_low() -> None:
    profile = ProfileView(skills={"Java": 5.0}, target_roles=["Java Developer"])
    jd = _extracted(required=["Python", "Django"], preferred=["Rust"], min_years=3)
    out = score_match(profile, jd, "Python Developer", Weights())
    assert out.score < 30
    assert set(out.missing_skills) == {"Python", "Django", "Rust"}
    assert any("resume" in s for s in out.suggestions)


def test_custom_weights_normalize() -> None:
    profile = ProfileView(skills={"Python": 5.0}, target_roles=[])
    jd = _extracted(required=["Python"], min_years=1)
    even = score_match(profile, jd, None, Weights(1, 1, 1, 1))
    # required 1.0, preferred 1.0, experience 1.0, title 0.5 → mean 0.875 → 88.
    assert even.score == 88


def test_experience_ratio() -> None:
    profile = ProfileView(skills={"Python": 2.0}, target_roles=[])
    jd = _extracted(required=["Python"], min_years=4)
    out = score_match(profile, jd, None, Weights())
    assert out.breakdown["experience"] == {
        "score": 50,
        "weight": 0.2,
        "profile_years": 2.0,
        "required_years": 4,
    }


def test_title_overlap_and_neutral() -> None:
    score, role = title_similarity("Senior Backend Engineer (Remote)", ["Backend Developer"])
    assert role == "Backend Developer"
    assert score == 0.5  # {backend} overlap / min(2,2)
    neutral, none_role = title_similarity(None, ["Backend Developer"])
    assert (neutral, none_role) == (0.5, None)
    no_roles, _ = title_similarity("Backend Engineer", [])
    assert no_roles == 0.5


def test_profile_view_canonicalizes_and_keeps_max_years() -> None:
    view = profile_view(
        [
            {"name": "postgres", "years": 2},
            {"name": "PostgreSQL", "years": 5},
            {"name": "not-a-real-skill", "years": 9},
        ],
        ["Data Engineer"],
    )
    assert view.skills == {"PostgreSQL": 5.0}
    assert view.target_roles == ["Data Engineer"]


def test_title_all_stopwords_neutral() -> None:
    score, role = title_similarity("Senior Remote", ["Backend Developer"])
    assert (score, role) == (0.5, None)


def test_role_all_stopwords_skipped() -> None:
    score, role = title_similarity("Backend Engineer", ["Senior", "Backend Guru"])
    assert (score, role) == (0.5, "Backend Guru")


def test_experience_gap_suggestion() -> None:
    profile = ProfileView(skills={"Python": 1.0}, target_roles=[])
    jd = _extracted(required=["Python"], min_years=5)
    out = score_match(profile, jd, None, Weights())
    assert any("Requires 5y" in s for s in out.suggestions)


def test_title_mismatch_suggestion() -> None:
    profile = ProfileView(skills={"Python": 5.0}, target_roles=["Data Analyst"])
    jd = _extracted(required=["Python"])
    out = score_match(profile, jd, "Embedded C++ Engineer", Weights())
    assert any("tailor your headline" in s for s in out.suggestions)


def test_zero_min_years_is_neutral() -> None:
    profile = ProfileView(skills={}, target_roles=[])
    out = score_match(profile, _extracted(min_years=0), None, Weights())
    exp = out.breakdown["experience"]
    assert isinstance(exp, dict) and exp["score"] == 100


def test_zero_weights_do_not_crash() -> None:
    profile = ProfileView(skills={"Python": 5.0}, target_roles=[])
    out = score_match(profile, _extracted(required=["Python"]), "x", Weights(0, 0, 0, 0))
    assert 0 <= out.score <= 100


def test_profile_view_ignores_non_numeric_years() -> None:
    view = profile_view([{"name": "Python", "years": "five"}], [])
    assert view.skills == {"Python": 0.0}


def test_llm_explainer_needs_client() -> None:
    from app.modules.match.explainer import LLMExplainer

    with pytest.raises(RuntimeError):
        LLMExplainer().explain(title=None, score=50, breakdown={}, missing_skills=[])


def test_llm_explainer_delegates_to_client() -> None:
    from app.modules.match.explainer import LLMExplainer

    class Client:
        def complete(self, prompt: str) -> str:
            assert "42/100" in prompt
            return "advice"

    out = LLMExplainer(Client()).explain(title="Dev", score=42, breakdown={}, missing_skills=["Go"])
    assert out == "advice"
