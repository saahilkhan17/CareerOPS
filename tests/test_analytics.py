"""Analytics endpoint tests: correctness, cache behavior, summary agreement."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import cache
from app.modules.analytics import service as analytics_service
from app.modules.ingestion import service as ingestion_service
from app.modules.ingestion.sources import RawListing
from tests.conftest import make_user


async def _headers(test_factory: async_sessionmaker[AsyncSession], email: str) -> dict[str, str]:
    _, headers = await make_user(test_factory, email)
    return headers


async def _seed(test_factory: async_sessionmaker[AsyncSession]) -> None:
    async def fetch() -> list[RawListing]:
        return [
            RawListing(
                source="remoteok",
                external_id="1",
                title="Backend Engineer",
                company="Acme",
                location="Remote",
                remote=True,
                salary_min=100000,
                salary_max=200000,
                currency="USD",
                description="Python and FastAPI required. 3 years of experience.",
            ),
            RawListing(
                source="remoteok",
                external_id="2",
                title="Backend Engineer",
                company="Globex",
                location="Remote",
                remote=True,
                salary_min=150000,
                salary_max=250000,
                currency="USD",
                description="Python and Django required.",
            ),
            RawListing(
                source="greenhouse",
                external_id="3",
                title="Designer",
                company="Initech",
                location="Berlin",
                remote=False,
                description="Figma and CSS.",
            ),
        ]

    await ingestion_service.run_ingestion("seed", test_factory, fetcher=fetch)
    await analytics_service.refresh_summary(test_factory)


async def test_skills_top_and_summary_agreement(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an1@example.com")
    await _seed(test_factory)

    resp = await client.get("/analytics/skills/top", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0] == {"skill": "Python", "postings": 2}
    assert body["total_skills"] >= 4

    # Filtered path goes live (summary stores no role/location splits).
    by_role = await client.get("/analytics/skills/top?role=designer", headers=headers)
    assert [i["skill"] for i in by_role.json()["items"]] == ["CSS", "Figma"]

    limited = await client.get("/analytics/skills/top?limit=1", headers=headers)
    assert len(limited.json()["items"]) == 1


async def test_top_served_from_cache_after_delete(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Cache proof: wipe the DB, the endpoint still serves the cached page."""
    headers = await _headers(test_factory, "an2@example.com")
    await _seed(test_factory)

    first = (await client.get("/analytics/skills/top", headers=headers)).json()

    async with test_factory() as session:
        from sqlalchemy import delete

        from app.modules.analytics.models import SkillDailyCount
        from app.modules.ingestion.models import Listing, ListingSkill

        await session.execute(delete(ListingSkill))
        await session.execute(delete(Listing))
        await session.execute(delete(SkillDailyCount))
        await session.commit()

    second = (await client.get("/analytics/skills/top", headers=headers)).json()
    assert second == first


async def test_import_invalidates_cache(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an3@example.com")
    await _seed(test_factory)

    before = (await client.get("/analytics/skills/top", headers=headers)).json()
    assert before["total_skills"] >= 1

    await client.post(
        "/listings/import",
        json={
            "format": "json",
            "records": [
                {"title": "Rust Engineer", "company": "Acme", "description": "Rust required."}
            ],
        },
        headers=headers,
    )
    after = (await client.get("/analytics/skills/top", headers=headers)).json()
    assert "Rust" in [i["skill"] for i in after["items"]]


async def test_cooccurrence(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an4@example.com")
    await _seed(test_factory)

    resp = await client.get("/analytics/skills/cooccurrence?skill=python", headers=headers)
    assert resp.status_code == 200
    names = [i["skill"] for i in resp.json()["items"]]
    assert "FastAPI" in names and "Django" in names
    assert "Python" not in names

    unknown = await client.get("/analytics/skills/cooccurrence?skill=cobol-xyz", headers=headers)
    assert unknown.status_code == 404


async def test_salary_stats_and_gate(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an5@example.com")
    await _seed(test_factory)

    resp = await client.get("/analytics/salary?min_n=1", headers=headers)
    stats = resp.json()["stats"]
    # Midpoints: (100k+200k)/2=150k, (150k+250k)/2=200k.
    assert stats == {"count": 2, "min": 150000, "median": 200000, "p75": 200000}

    gated = await client.get("/analytics/salary?min_n=5", headers=headers)
    assert gated.json()["stats"] == {
        "count": 2,
        "min": None,
        "median": None,
        "p75": None,
    }

    by_role = await client.get("/analytics/salary?role=designer&min_n=1", headers=headers)
    assert by_role.json()["stats"]["count"] == 0


async def test_trends_bucketing(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an6@example.com")
    await _seed(test_factory)

    week = await client.get("/analytics/trends", headers=headers)
    assert week.status_code == 200
    assert week.json()["granularity"] == "week"
    assert sum(p["postings"] for p in week.json()["points"]) == 3

    day = await client.get("/analytics/trends?granularity=day", headers=headers)
    assert sum(p["postings"] for p in day.json()["points"]) == 3

    month = await client.get("/analytics/trends?granularity=month", headers=headers)
    assert sum(p["postings"] for p in month.json()["points"]) == 3

    bad = await client.get("/analytics/trends?granularity=year", headers=headers)
    assert bad.status_code == 422


async def test_my_gap(client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]) -> None:
    headers = await _headers(test_factory, "an7@example.com")
    await _seed(test_factory)

    # No profile: everything in demand is a gap.
    open_gap = await client.get("/analytics/my-gap", headers=headers)
    assert open_gap.json()["items"][0]["skill"] == "Python"

    await client.put(
        "/profile",
        json={"skills": [{"name": "Python", "years": 5}], "target_roles": []},
        headers=headers,
    )
    # Profile edit invalidates my gap cache: Python drops out immediately.
    gap = await client.get("/analytics/my-gap", headers=headers)
    skills = [i["skill"] for i in gap.json()["items"]]
    assert "Python" not in skills
    assert skills[0] != "Python"


async def test_summary_refresh_rebuilds(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(test_factory)
    first = await analytics_service.refresh_summary(test_factory)
    assert first > 0
    second = await analytics_service.refresh_summary(test_factory)
    assert second == first  # deterministic full rebuild, no dupes

    cached = await cache.cache_get(cache.cache_key("skills-top", "x"))
    assert cached is None or isinstance(cached, dict)


async def test_anonymous_401(client: AsyncClient) -> None:
    assert (await client.get("/analytics/skills/top")).status_code == 401
    assert (await client.get("/analytics/my-gap")).status_code == 401


async def test_top_live_all_time_with_filter(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an11@example.com")
    await _seed(test_factory)
    resp = await client.get("/analytics/skills/top?role=engineer&days=0", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_skills"] >= 1


async def test_cache_fail_open_with_broken_client(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A Redis client that always raises: everything still serves."""
    from app.core import redis_client

    class Broken:
        async def get(self, *_: object) -> object:
            raise ConnectionError("redis gone")

        async def set(self, *_: object, **__: object) -> object:
            raise ConnectionError("redis gone")

        async def scan_iter(self, *_: object) -> object:
            raise ConnectionError("redis gone")
            yield  # pragma: no cover (unreachable, keeps it a generator)

    headers = await _headers(test_factory, "an12@example.com")
    await _seed(test_factory)
    redis_client.set_redis_client(Broken())
    try:
        assert (await client.get("/analytics/skills/top", headers=headers)).status_code == 200
        assert (await client.get("/analytics/my-gap", headers=headers)).status_code == 200
        await cache.cache_set("k", {"v": 1}, 10)
        assert await cache.cache_get("k") is None
        await cache.invalidate_analytics()
    finally:
        from fakeredis.aioredis import FakeRedis

        redis_client.set_redis_client(FakeRedis(decode_responses=True))


async def test_trends_empty_db(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an8@example.com")
    resp = await client.get("/analytics/trends", headers=headers)
    assert resp.json()["points"] == []
    top = await client.get("/analytics/skills/top", headers=headers)
    assert top.json() == {"items": [], "total_skills": 0}


def test_bucket_december_rollover() -> None:
    from app.modules.analytics.service import bucket_trends

    points = bucket_trends([("2025-12-20", 2), ("2026-01-05", 3)], "month")
    assert [p["bucket"] for p in points] == ["2025-12-01", "2026-01-01"]
    assert [p["postings"] for p in points] == [2, 3]


async def test_top_days_zero_means_all_time(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "an9@example.com")
    await _seed(test_factory)
    resp = await client.get("/analytics/skills/top?days=0", headers=headers)
    assert resp.json()["total_skills"] >= 4


async def test_fail_open_without_redis(
    client: AsyncClient,
    test_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Redis server: endpoints serve (cache skipped) and limits allow."""
    from app.core import redis_client

    headers = await _headers(test_factory, "an10@example.com")
    await _seed(test_factory)
    redis_client.set_redis_client(None)
    monkeypatch.setattr("app.core.rate_limit._limit_per_minute", lambda: 1)

    assert (await client.get("/analytics/skills/top", headers=headers)).status_code == 200
    assert (await client.get("/analytics/skills/top", headers=headers)).status_code == 200
    assert (await client.get("/applications", headers=headers)).status_code == 200
