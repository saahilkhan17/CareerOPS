"""Match endpoint tests (sqlite, no Docker)."""

import uuid as uuid_lib
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.match import service as match_service
from app.modules.match.explainer import set_explainer
from tests.conftest import make_user

JD_TEXT = """Backend Engineer.

Requirements:
- 3 years of experience with Python and FastAPI.
- PostgreSQL.

Nice to have:
- Docker.
"""


async def _headers(test_factory: async_sessionmaker[AsyncSession], email: str) -> dict[str, str]:
    _, headers = await make_user(test_factory, email)
    return headers


async def test_profile_crud(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "p1@example.com")
    assert (await client.get("/profile", headers=headers)).status_code == 404

    put = await client.put(
        "/profile",
        json={
            "skills": [{"name": "postgres", "years": 4}],
            "target_roles": ["Backend Engineer"],
            "education": "B.Tech",
            "preferences": {"remote": True},
        },
        headers=headers,
    )
    assert put.status_code == 200
    assert put.json()["skills"] == [{"name": "postgres", "years": 4.0}]
    assert put.json()["target_roles"] == ["Backend Engineer"]

    # Upsert replaces (no duplicate rows).
    put2 = await client.put(
        "/profile",
        json={"skills": [{"name": "Python", "years": 5}], "target_roles": []},
        headers=headers,
    )
    assert put2.json()["skills"] == [{"name": "Python", "years": 5.0}]
    got = await client.get("/profile", headers=headers)
    assert got.json()["skills"] == [{"name": "Python", "years": 5.0}]


async def test_match_pasted_scores_and_persists(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "m1@example.com")
    await client.put(
        "/profile",
        json={
            "skills": [
                {"name": "Python", "years": 5},
                {"name": "FastAPI", "years": 3},
                {"name": "PostgreSQL", "years": 4},
            ],
            "target_roles": ["Backend Engineer"],
        },
        headers=headers,
    )
    resp = await client.post(
        "/match", json={"title": "Backend Engineer", "text": JD_TEXT}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    # required 1.0, preferred 0.0 (Docker missing), experience 1.0, title 1.0
    # → 0.5 + 0 + 0.2 + 0.1 = 80.
    assert body["score"] == 80
    assert set(body["breakdown"].keys()) == {"required", "preferred", "experience", "title"}
    assert set(body["matched_skills"]) == {"Python", "FastAPI", "PostgreSQL"}
    assert "Docker" in body["missing_skills"]
    assert body["suggestions"]
    assert body["llm_explanation"] is None
    assert body["id"] and body["created_at"]

    history = await client.get("/match/history", headers=headers)
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["score"] == 80 and rows[0]["application_id"] is None


async def test_match_without_profile_uses_neutral(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "m2@example.com")
    resp = await client.post("/match", json={"text": JD_TEXT}, headers=headers)
    assert resp.status_code == 200
    assert 0 <= resp.json()["score"] <= 100


async def test_match_blank_400(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "m3@example.com")
    resp = await client.post("/match", json={"text": "   "}, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


async def test_match_application_links_and_title_default(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "m4@example.com")
    created = (
        await client.post(
            "/applications",
            json={"company": "Acme", "title": "Backend Engineer"},
            headers=headers,
        )
    ).json()
    resp = await client.post(f"/match/{created['id']}", json={"text": JD_TEXT}, headers=headers)
    assert resp.status_code == 200
    history = (await client.get("/match/history", headers=headers)).json()
    assert history[0]["application_id"] == created["id"]


async def test_match_application_isolation(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers_a = await _headers(test_factory, "a4@example.com")
    headers_b = await _headers(test_factory, "b4@example.com")
    created = (
        await client.post(
            "/applications",
            json={"company": "Acme", "title": "Dev"},
            headers=headers_a,
        )
    ).json()

    cross = await client.post(f"/match/{created['id']}", json={"text": JD_TEXT}, headers=headers_b)
    assert cross.status_code == 404

    missing = await client.post(
        f"/match/{uuid_lib.uuid4()}", json={"text": JD_TEXT}, headers=headers_a
    )
    assert missing.status_code == 404

    assert (await client.get("/match/history", headers=headers_b)).json() == []


async def test_match_application_blank_400(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "m6@example.com")
    created = (
        await client.post(
            "/applications",
            json={"company": "Acme", "title": "Dev"},
            headers=headers,
        )
    ).json()
    resp = await client.post(f"/match/{created['id']}", json={"text": "  "}, headers=headers)
    assert resp.status_code == 400


async def test_flag_on_without_explainer_stays_null(
    client: AsyncClient,
    test_factory: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    headers = await _headers(test_factory, "m7@example.com")
    monkeypatch.setattr(match_service, "llm_enabled", lambda: True)
    resp = await client.post("/match", json={"text": JD_TEXT}, headers=headers)
    assert resp.json()["llm_explanation"] is None


async def test_taxonomy_version(client: AsyncClient) -> None:
    resp = await client.get("/match/taxonomy-version")
    assert resp.json() == {"version": "2026.10.1"}


async def test_llm_explanation_flag_and_seam(
    client: AsyncClient,
    test_factory: async_sessionmaker[AsyncSession],
    monkeypatch: Any,
) -> None:
    headers = await _headers(test_factory, "m5@example.com")

    class FakeExplainer:
        def explain(self, **kwargs: Any) -> str:
            return f"fake advice for score {kwargs['score']}"

    # Flag off (default): explainer registered but unused.
    set_explainer(FakeExplainer())
    try:
        off = await client.post("/match", json={"text": JD_TEXT}, headers=headers)
        assert off.json()["llm_explanation"] is None
        score_off = off.json()["score"]

        # Flag on: explanation appears, score identical.
        monkeypatch.setattr(match_service, "llm_enabled", lambda: True)
        on = await client.post("/match", json={"text": JD_TEXT}, headers=headers)
        assert on.json()["llm_explanation"] == f"fake advice for score {score_off}"
        assert on.json()["score"] == score_off
    finally:
        set_explainer(None)


async def test_anonymous_401(client: AsyncClient) -> None:
    assert (await client.get("/profile")).status_code == 401
    assert (await client.post("/match", json={"text": JD_TEXT})).status_code == 401
