"""Endpoint benchmark: in-process TestClient + sqlite + fakeredis.

Measures real timings on this machine and writes docs/PERFORMANCE.md.
Nothing here is estimated — every number comes from a measured run.

Usage: .venv/Scripts/python scripts/bench.py
"""

import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.modules.analytics.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.match.models  # noqa: F401
import app.modules.tracker.models  # noqa: F401
from app.core import redis_client  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402

SKILLS = ["Python", "FastAPI", "PostgreSQL", "Docker", "React", "AWS", "Redis", "Django"]


def build_client() -> TestClient:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio

    asyncio.run(_create())

    from fakeredis.aioredis import FakeRedis

    redis_client.set_redis_client(FakeRedis(decode_responses=True))

    app = create_app()

    async def override() -> object:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    return TestClient(app, raise_server_exceptions=False)


def timeit(fn: object, repeats: int = 5) -> float:
    """Mean milliseconds over repeats (first warmup run discarded)."""
    call = fn  # type: ignore[operator]
    call()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.mean(samples)


def main() -> None:
    client = build_client()
    headers: dict[str, str] = {}

    client.post("/auth/register", json={"email": "bench@example.com", "password": "password123"})
    login = client.post(
        "/auth/login", json={"email": "bench@example.com", "password": "password123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    for i in range(50):
        client.post(
            "/applications",
            json={"company": f"Co{i % 10}", "title": f"Engineer {i}"},
            headers=headers,
        )

    batch: list[dict[str, str]] = []
    for i in range(300):
        skill = SKILLS[i % len(SKILLS)]
        batch.append(
            {
                "title": f"{skill} Developer {i}",
                "company": f"Corp{i % 15}",
                "description": f"{skill} and Python required. 3 years of experience.",
            }
        )
    for chunk in (batch[:100], batch[100:200], batch[200:]):
        resp = client.post(
            "/listings/import", json={"format": "json", "records": chunk}, headers=headers
        )
        assert resp.status_code == 200, resp.text

    client.put(
        "/profile",
        json={"skills": [{"name": "Python", "years": 5}], "target_roles": ["Engineer"]},
        headers=headers,
    )

    jd = "Backend Engineer.\nRequirements:\n- Python and FastAPI.\nNice to have:\n- Docker."

    results: list[tuple[str, float]] = [
        ("GET /health", timeit(lambda: client.get("/health"))),
        (
            "GET /applications?limit=20",
            timeit(lambda: client.get("/applications?limit=20", headers=headers)),
        ),
        (
            "POST /match",
            timeit(lambda: client.post("/match", json={"text": jd}, headers=headers)),
        ),
        (
            "GET /listings?limit=20",
            timeit(lambda: client.get("/listings?limit=20", headers=headers)),
        ),
    ]

    # Cold: clear the cache before every sample so each hit recomputes.
    import asyncio

    async def _clear() -> None:
        from app.core import cache as cache_module

        await cache_module.invalidate_analytics()

    cold_samples = []
    for _ in range(3):
        asyncio.run(_clear())
        start = time.perf_counter()
        client.get("/analytics/skills/top", headers=headers)
        cold_samples.append((time.perf_counter() - start) * 1000.0)
    results.append(("GET /analytics/skills/top (cold)", statistics.mean(cold_samples)))
    results.append(
        (
            "GET /analytics/skills/top (warm)",
            timeit(lambda: client.get("/analytics/skills/top", headers=headers)),
        )
    )
    results.append(
        ("GET /analytics/my-gap", timeit(lambda: client.get("/analytics/my-gap", headers=headers)))
    )

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Performance (measured, not estimated)",
        "",
        f"Measured: {stamp} · sqlite (in-process) · 50 applications · 300 listings",
        "",
        "| Endpoint | Mean ms |",
        "|---|---|",
    ]
    print(f"{'endpoint':45s} {'mean ms':>10s}")
    for name, ms in results:
        print(f"{name:45s} {ms:10.1f}")
        lines.append(f"| {name} | {ms:.1f} |")
    lines += [
        "",
        "Method: scripts/bench.py (TestClient + sqlite StaticPool + fakeredis,",
        "mean of 5 runs after warmup; cold = cache cleared first).",
        "Re-run to refresh: `.venv/Scripts/python scripts/bench.py`.",
        "PG + Redis numbers pending Docker on this machine.",
    ]
    Path("docs/PERFORMANCE.md").write_text("\n".join(lines) + "\n")
    print("wrote docs/PERFORMANCE.md")


if __name__ == "__main__":
    main()
