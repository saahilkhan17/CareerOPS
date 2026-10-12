"""Seed script tests: full demo dataset + idempotent rerun (sqlite file DB)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.modules.analytics.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.match.models  # noqa: F401
import app.modules.tracker.models  # noqa: F401
from app.db.base import Base
from app.modules.auth.models import User
from app.modules.ingestion.models import Listing
from app.modules.match.models import MatchResult, Profile
from app.modules.tracker.models import JobApplication, Note, Reminder, StatusHistory


def _load_seed() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "seedmod", Path(__file__).parent.parent / "scripts" / "seed.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def _counts(factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    async with factory() as session:
        return {
            "users": await _count(session, User),
            "profiles": await _count(session, Profile),
            "applications": await _count(session, JobApplication),
            "history": await _count(session, StatusHistory),
            "notes": await _count(session, Note),
            "reminders": await _count(session, Reminder),
            "listings": await _count(session, Listing),
            "matches": await _count(session, MatchResult),
        }


async def test_seed_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seed = _load_seed()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/demo.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(seed, "get_session_factory", lambda: factory)

    await seed.main()
    first = await _counts(factory)
    assert first == {
        "users": 1,
        "profiles": 1,
        "applications": 8,
        "history": 22,
        "notes": 2,
        "reminders": 2,
        "listings": 12,
        "matches": 2,
    }
    out = capsys.readouterr().out
    assert "demo@careerops.dev" in out

    await seed.main()  # rerun: clean skip, identical counts
    assert await _counts(factory) == first
    assert "already exists" in capsys.readouterr().out
    await engine.dispose()
