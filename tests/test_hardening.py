"""Hardening tests: rate limits, audit trail, validation envelope, logging."""

import json
import logging

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import rate_limit
from app.core.logging import JsonFormatter
from app.modules.audit.models import AuditLog
from tests.conftest import PASSWORD, make_user


async def _audit_count(test_factory: async_sessionmaker[AsyncSession]) -> int:
    async with test_factory() as session:
        return await session.scalar(select(func.count()).select_from(AuditLog)) or 0


async def test_audit_trail_records_actions(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    before = await _audit_count(test_factory)

    await client.post("/auth/register", json={"email": "audit@example.com", "password": PASSWORD})
    login = await client.post(
        "/auth/login", json={"email": "audit@example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = await client.post(
        "/applications",
        json={"company": "Acme", "title": "Dev"},
        headers=headers,
    )
    app_id = created.json()["id"]
    await client.post(
        f"/applications/{app_id}/status", json={"to_status": "applied"}, headers=headers
    )
    await client.put("/profile", json={"skills": [{"name": "Python"}]}, headers=headers)
    await client.post(
        "/listings/import",
        json={"format": "json", "records": [{"title": "T", "company": "C"}]},
        headers=headers,
    )

    async with test_factory() as session:
        rows = (
            (await session.execute(select(AuditLog.action).order_by(AuditLog.created_at)))
            .scalars()
            .all()
        )
    new_actions = rows[before:]
    for expected in (
        "auth.register",
        "auth.login",
        "tracker.application.create",
        "tracker.application.status",
        "match.profile.upsert",
        "ingestion.import",
    ):
        assert expected in new_actions, new_actions

    async with test_factory() as session:
        sample = (await session.execute(select(AuditLog).limit(1))).scalar_one()
        assert sample.user_id is not None and sample.entity


async def test_rate_limit_blocks_with_envelope(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "_limit_per_minute", lambda: 2)

    for _ in range(2):
        resp = await client.get("/applications")
        assert resp.status_code == 401  # counted, but not limited yet
    blocked = await client.get("/applications")
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"]["code"] == "rate_limited"
    assert "Retry-After" in blocked.headers
    assert "X-Request-ID" in blocked.headers


async def test_rate_limit_skips_health(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "_limit_per_minute", lambda: 1)
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/health")).status_code == 200


async def test_rate_limit_identity_buckets(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.core.rate_limit import allowed, identity

    user_a, headers_a = await make_user(test_factory, "rl-a@example.com")
    await make_user(test_factory, "rl-b@example.com")

    assert await allowed("test-id-1", 1) == (True, 0)
    assert (await allowed("test-id-1", 1))[0] is False
    assert await allowed("test-id-2", 1) == (True, 0)

    from starlette.requests import Request as StarletteRequest

    def _request(auth_headers: dict[str, str]) -> StarletteRequest:
        raw = [(k.lower().encode(), v.encode()) for k, v in auth_headers.items()]
        return StarletteRequest(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": raw,
                "client": ("testclient", 50000),
            }
        )

    assert identity(_request(headers_a)) == f"user:{user_a.id}"
    assert identity(_request({})).startswith("ip:")


async def test_validation_error_envelope(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json={"email": "not-an-email", "password": "x"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["details"][0]["loc"]
    # Details are JSON-safe (no raw exception objects).
    json.dumps(body)


def test_json_formatter_duration_ms() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", (), None)
    plain = json.loads(JsonFormatter().format(record))
    assert "duration_ms" not in plain
    record2 = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", (), None)
    record2.duration_ms = 12
    assert json.loads(JsonFormatter().format(record2))["duration_ms"] == 12


async def test_celery_signal_receivers(caplog: pytest.LogCaptureFixture) -> None:
    from app.workers.celery import log_task_failure, log_task_outcome

    class Sender:
        name = "ingest_source"

    with caplog.at_level(logging.INFO, logger="careerops.worker"):
        log_task_outcome(Sender(), task_id="t1", state="SUCCESS")
        log_task_failure(Sender(), task_id="t2", exception=ValueError("boom"))
    assert "task finished" in caplog.text and "task failed" in caplog.text
