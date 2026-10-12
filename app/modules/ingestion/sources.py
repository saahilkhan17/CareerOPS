"""Listing source adapters behind one interface. Public JSON APIs only."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class RawListing:
    """Unvalidated normalized listing from a source adapter."""

    source: str
    external_id: str
    title: str
    company: str
    location: str | None = None
    remote: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    description: str | None = None
    url: str | None = None
    posted_at: datetime | None = None


class ListingSource(Protocol):
    """Common interface every source adapter implements."""

    name: str

    async def fetch(self, client: httpx.AsyncClient) -> list[RawListing]:
        """Fetch and normalize raw listings. Raises on unrecoverable errors."""
        ...


class RateLimiter:
    """Per-source minimum interval between HTTP calls (per-process)."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleeper
        self._last: dict[str, float] = {}

    async def throttle(self, key: str) -> None:
        """Sleep just enough to honor the minimum interval for key."""
        now = self._clock()
        wait = self._min_interval - (now - self._last.get(key, 0.0))
        self._last[key] = now + max(0.0, wait)
        if wait > 0:
            await self._sleep(wait)


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    backoff: float = 1.0,
    limiter: RateLimiter | None = None,
    source_key: str = "",
) -> object:
    """GET JSON with retries on transport errors / 5xx / 429.

    Raises the last httpx error when retries run out. backoff=0 disables
    sleeping (tests).
    """
    if limiter is not None:
        await limiter.throttle(source_key or url)
    attempt = 0
    while True:
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.TransportError:
            if attempt >= retries:
                raise
            attempt += 1
            if backoff > 0:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            continue
        if response.status_code in RETRYABLE_STATUS and attempt < retries:
            attempt += 1
            if backoff > 0:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            continue
        # Exhausted retries surface the real HTTP error; other statuses
        # (e.g. 404) raise here on first sight and propagate untouched.
        response.raise_for_status()
        return response.json()


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def parse_iso_datetime(value: object) -> datetime | None:
    """Parse ISO-8601 / epoch seconds / epoch millis, else None."""
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            stamp = float(value)
            if stamp > 1e12:  # millis
                stamp /= 1000.0
            return datetime.fromtimestamp(stamp, tz=UTC).replace(tzinfo=None)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return _naive_utc(datetime.fromisoformat(text))
    except (ValueError, OverflowError, OSError):
        return None
    return None


def looks_remote(location: str | None) -> bool:
    """Heuristic remote flag from free-text location."""
    return location is not None and "remote" in location.lower()


class GreenhouseSource:
    """Greenhouse public board API (per-board company names from config)."""

    name = "greenhouse"

    def __init__(
        self,
        boards: dict[str, str],
        retries: int = 3,
        backoff: float = 1.0,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._boards = boards
        self._retries = retries
        self._backoff = backoff
        self._limiter = limiter

    async def fetch(self, client: httpx.AsyncClient) -> list[RawListing]:
        out: list[RawListing] = []
        for token, company in self._boards.items():
            payload = await fetch_json(
                client,
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                retries=self._retries,
                backoff=self._backoff,
                limiter=self._limiter,
                source_key=self.name,
            )
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                job_id = job.get("id")
                title = job.get("title")
                if job_id is None or not title:
                    continue
                location = job.get("location") or {}
                loc_name = location.get("name") if isinstance(location, dict) else None
                out.append(
                    RawListing(
                        source=self.name,
                        external_id=str(job_id),
                        title=str(title),
                        company=company,
                        location=str(loc_name) if loc_name else None,
                        remote=looks_remote(str(loc_name) if loc_name else None),
                        description=None,
                        url=str(job["absolute_url"]) if job.get("absolute_url") else None,
                        posted_at=parse_iso_datetime(
                            job.get("updated_at") or job.get("created_at")
                        ),
                    )
                )
        return out


def _lever_salary(value: object) -> tuple[int | None, int | None, str | None]:
    if isinstance(value, dict):
        lo = value.get("min")
        hi = value.get("max")
        cur = value.get("currency")
        try:
            lo_i = int(lo) if lo is not None else None
            hi_i = int(hi) if hi is not None else None
        except (TypeError, ValueError):
            return None, None, None
        currency = str(cur).upper() if cur else ("USD" if lo_i or hi_i else None)
        return lo_i, hi_i, currency
    return None, None, None


class LeverSource:
    """Lever public postings API (per-slug company names from config)."""

    name = "lever"

    def __init__(
        self,
        companies: dict[str, str],
        retries: int = 3,
        backoff: float = 1.0,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._companies = companies
        self._retries = retries
        self._backoff = backoff
        self._limiter = limiter

    async def fetch(self, client: httpx.AsyncClient) -> list[RawListing]:
        out: list[RawListing] = []
        for slug, company in self._companies.items():
            payload = await fetch_json(
                client,
                f"https://api.lever.co/v0/postings/{slug}",
                retries=self._retries,
                backoff=self._backoff,
                limiter=self._limiter,
                source_key=self.name,
            )
            postings = payload if isinstance(payload, list) else []
            for post in postings:
                if not isinstance(post, dict):
                    continue
                post_id = post.get("id")
                title = post.get("text")
                if post_id is None or not title:
                    continue
                cats = post.get("categories") or {}
                loc = cats.get("location") if isinstance(cats, dict) else None
                remote = post.get("workplaceType") == "remote" or looks_remote(
                    str(loc) if loc else None
                )
                lo, hi, cur = _lever_salary(post.get("salaryRange"))
                description = post.get("descriptionPlain") or post.get("description")
                out.append(
                    RawListing(
                        source=self.name,
                        external_id=str(post_id),
                        title=str(title),
                        company=company,
                        location=str(loc) if loc else None,
                        remote=remote,
                        salary_min=lo,
                        salary_max=hi,
                        currency=cur,
                        description=str(description) if description else None,
                        url=str(post["applyUrl"]) if post.get("applyUrl") else None,
                        posted_at=parse_iso_datetime(post.get("createdAt")),
                    )
                )
        return out


class RemoteOKSource:
    """RemoteOK public feed (no auth; all listings remote)."""

    name = "remoteok"

    def __init__(
        self,
        retries: int = 3,
        backoff: float = 1.0,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._retries = retries
        self._backoff = backoff
        self._limiter = limiter

    async def fetch(self, client: httpx.AsyncClient) -> list[RawListing]:
        payload = await fetch_json(
            client,
            "https://remoteok.com/api",
            headers={"User-Agent": "careerops/0.1"},
            retries=self._retries,
            backoff=self._backoff,
            limiter=self._limiter,
            source_key=self.name,
        )
        items = payload if isinstance(payload, list) else []
        out: list[RawListing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            job_id = item.get("id")
            title = item.get("position")
            if job_id is None or not title:
                continue
            lo = item.get("salary_min")
            hi = item.get("salary_max")
            out.append(
                RawListing(
                    source=self.name,
                    external_id=str(job_id),
                    title=str(title),
                    company=str(item.get("company", "Unknown")),
                    location=str(item["location"]) if item.get("location") else None,
                    remote=True,
                    salary_min=int(lo) if isinstance(lo, (int, float)) else None,
                    salary_max=int(hi) if isinstance(hi, (int, float)) else None,
                    currency="USD" if lo or hi else None,
                    description=str(item["description"]) if item.get("description") else None,
                    url=str(item["url"]) if item.get("url") else None,
                    posted_at=parse_iso_datetime(item.get("epoch") or item.get("date")),
                )
            )
        return out


SOURCES: dict[str, type[GreenhouseSource] | type[LeverSource] | type[RemoteOKSource]] = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "remoteok": RemoteOKSource,
}
