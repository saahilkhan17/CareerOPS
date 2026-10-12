"""Adapter parsing + HTTP retry/throttle/date parsing (respx, no network)."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx

from app.modules.ingestion.sources import (
    GreenhouseSource,
    LeverSource,
    RateLimiter,
    RemoteOKSource,
    fetch_json,
    looks_remote,
    parse_iso_datetime,
)

FIX = Path(__file__).parent / "fixtures" / "sources"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


async def test_greenhouse_parsing() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://boards-api.greenhouse.io/v1/boards/demo/jobs").mock(
                return_value=httpx.Response(200, json=load("greenhouse.json"))
            )
            out = await GreenhouseSource({"demo": "Demo Inc"}).fetch(http)
    assert len(out) == 2
    first, second = out
    assert (first.title, first.company, first.external_id) == (
        "Backend Engineer (Python)",
        "Demo Inc",
        "111",
    )
    assert first.remote is True
    assert first.posted_at == datetime(2026, 9, 20, 14, 0, 0)  # -04:00 → UTC naive
    assert first.description is None and first.salary_min is None
    assert second.remote is False and second.location == "New York, NY"


async def test_lever_parsing() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://api.lever.co/v0/postings/demo").mock(
                return_value=httpx.Response(200, json=load("lever.json"))
            )
            out = await LeverSource({"demo": "Demo Co"}).fetch(http)
    assert len(out) == 2
    first, second = out
    assert (first.salary_min, first.salary_max, first.currency) == (150000, 200000, "USD")
    assert first.remote is True
    assert first.description == "Python and PostgreSQL required. 5 years of experience."
    assert first.posted_at == datetime(2024, 9, 25, 0, 0, 0)  # millis → UTC naive
    assert (second.salary_min, second.currency) == (None, None)
    assert second.remote is False


async def test_remoteok_parsing_and_bad_item_dropped() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://remoteok.com/api").mock(
                return_value=httpx.Response(200, json=load("remoteok.json"))
            )
            out = await RemoteOKSource().fetch(http)
    assert len(out) == 2  # legal-notice item without position/id dropped
    first, second = out
    assert (first.company, first.remote) == ("Acme", True)
    assert (first.salary_min, first.salary_max, first.currency) == (120000, 160000, "USD")
    assert first.posted_at == datetime(2026, 9, 25, 8, 0, 0)
    assert (second.salary_min, second.currency) == (None, None)


async def test_fetch_json_retries_then_succeeds() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://example.com/jobs").mock(
                side_effect=[
                    httpx.Response(500),
                    httpx.Response(503),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            out = await fetch_json(http, "https://example.com/jobs", backoff=0)
    assert out == {"ok": True}
    assert route.call_count == 3


async def test_fetch_json_retries_429() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://example.com/r").mock(
                side_effect=[
                    httpx.Response(429),
                    httpx.Response(200, json=[]),
                ]
            )
            out = await fetch_json(http, "https://example.com/r", backoff=0)
    assert out == []
    assert route.call_count == 2


async def test_fetch_json_exhausts_retries() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://example.com/x").mock(side_effect=httpx.ConnectError("down"))
            with pytest.raises(httpx.ConnectError):
                await fetch_json(http, "https://example.com/x", retries=2, backoff=0)


async def test_fetch_json_client_error_not_retried() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://example.com/404").mock(return_value=httpx.Response(404))
            with pytest.raises(httpx.HTTPStatusError):
                await fetch_json(http, "https://example.com/404", backoff=0)
    assert route.call_count == 1


async def test_rate_limiter_enforces_interval() -> None:
    now = [100.0]
    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)

    limiter = RateLimiter(1.0, clock=lambda: now[0], sleeper=sleep)
    await limiter.throttle("gh")
    assert slept == []
    now[0] += 0.2
    await limiter.throttle("gh")
    assert slept == [pytest.approx(0.8)]
    # Different key unaffected.
    await limiter.throttle("lever")
    assert len(slept) == 1


def test_parse_iso_datetime_variants() -> None:
    assert parse_iso_datetime("2026-09-18T09:00:00Z") == datetime(2026, 9, 18, 9, 0, 0)
    assert parse_iso_datetime(1758787200) == datetime(2025, 9, 25, 8, 0, 0)
    assert parse_iso_datetime(1727000000000) == datetime(2024, 9, 22, 10, 13, 20)
    assert parse_iso_datetime("garbage") is None
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime(True) is None


def test_looks_remote() -> None:
    assert looks_remote("Remote") is True
    assert looks_remote("Remote, USA") is True
    assert looks_remote("Berlin") is False
    assert looks_remote(None) is False


async def test_fetch_json_sleeps_between_retries() -> None:
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get("https://example.com/flaky").mock(
                side_effect=[
                    httpx.ConnectError("blip"),
                    httpx.Response(500),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            out = await fetch_json(http, "https://example.com/flaky", retries=3, backoff=0.01)
    assert out == {"ok": True}
    assert route.call_count == 3


async def test_fetch_json_honors_limiter() -> None:
    now = [50.0]
    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)

    limiter = RateLimiter(2.0, clock=lambda: now[0], sleeper=sleep)
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://example.com/l").mock(return_value=httpx.Response(200, json=[]))
            await fetch_json(http, "https://example.com/l", limiter=limiter)
            await fetch_json(http, "https://example.com/l", limiter=limiter)
    assert slept == [2.0]


async def test_greenhouse_skips_malformed_jobs() -> None:
    payload = {
        "jobs": [
            "junk",
            {"id": 7},
            {"title": "No ID here"},
            {
                "id": 8,
                "title": "Dev",
                "location": {"name": "Remote"},
                "absolute_url": "https://x/y",
            },
        ]
    }
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://boards-api.greenhouse.io/v1/boards/d/jobs").mock(
                return_value=httpx.Response(200, json=payload)
            )
            out = await GreenhouseSource({"d": "D Co"}).fetch(http)
    assert [(r.external_id, r.title) for r in out] == [("8", "Dev")]


async def test_lever_bad_salary_and_malformed_posts() -> None:
    payload = [
        "junk",
        {},
        {
            "id": "b1",
            "text": "Dev",
            "salaryRange": {"min": "lots", "max": None},
            "createdAt": 1727222400000,
        },
        {"id": "b2", "text": "Dev2", "salaryRange": "high"},
    ]
    async with httpx.AsyncClient() as http:
        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://api.lever.co/v0/postings/d").mock(
                return_value=httpx.Response(200, json=payload)
            )
            out = await LeverSource({"d": "D Co"}).fetch(http)
    assert len(out) == 2
    assert all((r.salary_min, r.salary_max, r.currency) == (None, None, None) for r in out)
