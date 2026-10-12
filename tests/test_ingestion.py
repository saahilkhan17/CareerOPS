"""Ingestion pipeline, auto-match, and Celery wiring tests (sqlite, no Redis)."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ingestion import service
from app.modules.ingestion.models import IngestionRun, Listing, ListingSkill
from app.modules.ingestion.sources import RawListing
from app.modules.match.models import MatchResult
from tests.conftest import make_user


def raw(
    source: str = "greenhouse",
    external_id: str = "1",
    title: str = "Backend Engineer",
    company: str = "Acme",
    description: str | None = "Python and PostgreSQL required.",
) -> RawListing:
    return RawListing(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        description=description,
    )


async def _counts(
    test_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int, int]:
    async with test_factory() as session:
        listings = await session.scalar(select(func.count()).select_from(Listing))
        skills = await session.scalar(select(func.count()).select_from(ListingSkill))
        runs = await session.scalar(select(func.count()).select_from(IngestionRun))
    return listings or 0, skills or 0, runs or 0


async def test_pipeline_inserts_and_tags_skills(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fetch() -> list[RawListing]:
        return [raw(), raw(external_id="2", title="Frontend Dev", description="React and CSS.")]

    stats = await service.run_ingestion("greenhouse", test_factory, fetcher=fetch)
    assert stats == {"fetched": 2, "inserted": 2, "skipped": 0, "errors": 0}

    async with test_factory() as session:
        listing = (
            await session.execute(select(Listing).where(Listing.external_id == "1"))
        ).scalar_one()
        assert listing.company == "Acme"
        skills = (
            (
                await session.execute(
                    select(ListingSkill.skill).where(ListingSkill.listing_id == listing.id)
                )
            )
            .scalars()
            .all()
        )
        assert {"Python", "PostgreSQL"} <= set(skills)

        run = (await session.execute(select(IngestionRun))).scalar_one()
        assert (run.fetched, run.inserted, run.skipped, run.errors) == (2, 2, 0, 0)
        assert run.finished_at is not None and run.error_detail is None


async def test_pipeline_idempotent_rerun(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fetch() -> list[RawListing]:
        return [raw()]

    first = await service.run_ingestion("greenhouse", test_factory, fetcher=fetch)
    second = await service.run_ingestion("greenhouse", test_factory, fetcher=fetch)
    assert (first["inserted"], first["skipped"]) == (1, 0)
    assert (second["inserted"], second["skipped"]) == (0, 1)
    assert await _counts(test_factory) == (1, 2, 2)


async def test_cross_source_content_hash_dedup(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fetch_a() -> list[RawListing]:
        return [raw(source="greenhouse", external_id="1")]

    async def fetch_b() -> list[RawListing]:
        return [raw(source="lever", external_id="9")]  # same content, other source

    await service.run_ingestion("greenhouse", test_factory, fetcher=fetch_a)
    stats = await service.run_ingestion("lever", test_factory, fetcher=fetch_b)
    assert (stats["inserted"], stats["skipped"]) == (0, 1)


async def test_unknown_source_records_error(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    stats = await service.run_ingestion("nope", test_factory)
    assert stats["errors"] == 1
    async with test_factory() as session:
        run = (await session.execute(select(IngestionRun))).scalar_one()
        assert run.errors == 1 and "unknown source" in (run.error_detail or "")


async def test_fetch_failure_records_run(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def boom() -> list[RawListing]:
        raise ConnectionError("dns down")

    stats = await service.run_ingestion("lever", test_factory, fetcher=boom)
    assert stats == {"fetched": 0, "inserted": 0, "skipped": 0, "errors": 1}
    async with test_factory() as session:
        run = (await session.execute(select(IngestionRun))).scalar_one()
        assert run.finished_at is not None
        assert "ConnectionError" in (run.error_detail or "")


async def test_clean_html_and_hash() -> None:
    assert service.clean_html("<p>Python &amp; <b>Django</b></p>") == "Python & Django"
    assert service.clean_html(None) is None
    assert service.clean_html("   ") is None
    assert service.content_hash("A", "B", None) == service.content_hash(" a ", "b", "")
    assert service.content_hash("A", "B", "x") != service.content_hash("A", "B", "y")


async def test_auto_match_creates_then_idempotent(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    user, _ = await make_user(test_factory, "am@example.com")
    async with test_factory() as session:
        from app.modules.match.models import Profile

        session.add(
            Profile(
                user_id=user.id,
                skills=[{"name": "Python", "years": 5}],
                target_roles=["Backend Engineer"],
            )
        )
        await session.commit()

    async def fetch() -> list[RawListing]:
        return [
            raw(external_id="1", title="Backend Engineer"),
            raw(external_id="2", title="Data Analyst", description="SQL and Pandas."),
        ]

    await service.run_ingestion("remoteok", test_factory, fetcher=fetch)
    first = await service.auto_match(test_factory)
    assert first == {"users": 1, "scored": 2}

    async with test_factory() as session:
        rows = (
            (await session.execute(select(MatchResult).where(MatchResult.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert all(r.listing_id is not None for r in rows)
        by_title = {r.title: r.score for r in rows}
        assert by_title["Backend Engineer"] > by_title["Data Analyst"]

    second = await service.auto_match(test_factory)
    assert second == {"users": 0, "scored": 0}


async def test_auto_match_skips_users_without_profile(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    await make_user(test_factory, "noprofile@example.com")

    async def fetch() -> list[RawListing]:
        return [raw()]

    await service.run_ingestion("remoteok", test_factory, fetcher=fetch)
    assert await service.auto_match(test_factory) == {"users": 0, "scored": 0}


def test_celery_wiring_without_broker() -> None:
    from app.workers import tasks  # noqa: F401 (import side effect: registers tasks)
    from app.workers.celery import celery

    ingest = celery.tasks["ingest_source"]
    auto = celery.tasks["auto_match"]
    assert ingest.max_retries == 3 and ingest.retry_backoff is True
    assert auto.max_retries == 3
    assert getattr(ingest, "autoretry_for", None) == (Exception,)

    schedule = celery.conf.beat_schedule
    assert set(schedule) == {
        "ingest-greenhouse-daily",
        "ingest-lever-daily",
        "ingest-remoteok-daily",
        "auto-match-nightly",
    }
    assert schedule["ingest-greenhouse-daily"]["args"] == ("greenhouse",)
    assert schedule["auto-match-nightly"]["task"] == "auto_match"


async def test_run_ingestion_live_adapter_path(
    test_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E2E through build_sources + real HTTP (respx): covers adapter wiring."""
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "sources" / "greenhouse.json").read_text()
    )
    stub = SimpleNamespace(
        ingest_greenhouse_boards={"demo": "Demo Inc"},
        ingest_lever_companies={},
        ingest_remoteok_enabled=False,
        ingest_http_retries=2,
        ingest_http_backoff=0,
        ingest_min_interval=0,
    )
    monkeypatch.setattr(service, "get_settings", lambda: stub)
    assert set(service.build_sources()) == {"greenhouse", "lever"}

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://boards-api.greenhouse.io/v1/boards/demo/jobs").mock(
            return_value=httpx.Response(200, json=payload)
        )
        stats = await service.run_ingestion("greenhouse", test_factory)
    assert (stats["fetched"], stats["inserted"]) == (2, 2)


async def test_preferred_skills_tagged_not_required(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fetch() -> list[RawListing]:
        return [
            raw(
                description="Python required.\nNice to have: Docker.",
            )
        ]

    await service.run_ingestion("greenhouse", test_factory, fetcher=fetch)
    async with test_factory() as session:
        rows = (await session.execute(select(ListingSkill))).scalars().all()
        by_skill = {r.skill: r.required for r in rows}
    assert by_skill == {"Python": True, "Docker": False}


async def test_auto_match_respects_limit(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    user, _ = await make_user(test_factory, "cap@example.com")
    user2, _ = await make_user(test_factory, "cap2@example.com")
    async with test_factory() as session:
        from app.modules.match.models import Profile

        session.add(Profile(user_id=user.id, skills=[], target_roles=[]))
        session.add(Profile(user_id=user2.id, skills=[], target_roles=[]))
        await session.commit()

    async def fetch() -> list[RawListing]:
        return [
            raw(external_id="1", title="Backend One"),
            raw(external_id="2", title="Backend Two", description="Django required."),
            raw(external_id="3", title="Backend Three", description="Flask required."),
        ]

    await service.run_ingestion("remoteok", test_factory, fetcher=fetch)
    # Cap hit mid-loop: second profile never processed (break).
    assert await service.auto_match(test_factory, limit=1) == {"users": 1, "scored": 1}
    # Next run: user1 has 2 left, user2 has 3 left.
    assert await service.auto_match(test_factory) == {"users": 2, "scored": 5}


async def test_auto_match_skips_orphan_profile_and_blank_listing(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    import uuid as uuid_lib

    from app.modules.ingestion.models import Listing
    from app.modules.match.models import Profile

    user, _ = await make_user(test_factory, "real@example.com")
    async with test_factory() as session:
        # Profile whose user does not exist (stale row).
        session.add(Profile(user_id=uuid_lib.uuid4(), skills=[], target_roles=[]))
        session.add(Profile(user_id=user.id, skills=[], target_roles=[]))
        # Listing with blank text: extraction fails, row skipped, run survives.
        session.add(
            Listing(
                source="import",
                external_id="blank-1",
                title="",
                company="Acme",
                content_hash="deadbeef",
            )
        )
        await session.commit()

    assert await service.auto_match(test_factory) == {"users": 1, "scored": 0}


async def test_pipeline_counts_item_failures(
    test_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}
    original = service._insert_listing

    async def flaky(session: AsyncSession, raw: RawListing) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return await original(session, raw)

    monkeypatch.setattr(service, "_insert_listing", flaky)

    async def fetch() -> list[RawListing]:
        return [raw(external_id="1"), raw(external_id="2")]

    stats = await service.run_ingestion("greenhouse", test_factory, fetcher=fetch)
    assert stats == {"fetched": 2, "inserted": 1, "skipped": 0, "errors": 1}
