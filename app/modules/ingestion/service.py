"""Ingestion pipeline: fetch → normalize → dedupe → skill-tag, with a ledger."""

import hashlib
import html
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.cache import invalidate_analytics
from app.core.config import get_settings
from app.core.time import utcnow
from app.modules.audit import repository as audit_repository
from app.modules.auth.models import User
from app.modules.ingestion import sources
from app.modules.ingestion.models import IngestionRun, Listing, ListingSkill
from app.modules.ingestion.sources import ListingSource, RateLimiter, RawListing
from app.modules.match import scorer as match_scorer
from app.modules.match import service as match_service
from app.modules.match.extractor import extract
from app.modules.match.models import MatchResult, Profile

logger = logging.getLogger("careerops.ingestion")

TAG_RE = re.compile(r"<[^>]+>")

MAX_IMPORT_RECORDS = 2000


def clean_html(value: str | None) -> str | None:
    """Strip HTML tags/entities from source descriptions (regex, deterministic)."""
    if not value:
        return None
    text = TAG_RE.sub(" ", value)
    text = html.unescape(text)
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed or None


def content_hash(title: str, company: str, description: str | None) -> str:
    """Cross-source dedup key over normalized core fields."""
    normalized = "|".join(
        [title.strip().lower(), company.strip().lower(), (description or "").strip().lower()]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


CSV_COLUMNS = ("title", "company", "location", "description", "url", "posted_at")


def parse_import_csv(csv_text: str) -> list[dict[str, str | None]]:
    """Parse CSV import text into record dicts. Raises ValueError on bad input."""
    import csv
    import io

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
    except Exception as exc:
        raise ValueError(f"unreadable CSV: {exc}") from None
    headers = reader.fieldnames or []
    missing = [c for c in ("title", "company") if c not in headers]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")
    records: list[dict[str, str | None]] = []
    for row in reader:
        title = (row.get("title") or "").strip()
        company = (row.get("company") or "").strip()
        if not title or not company:
            continue
        records.append({col: (row.get(col) or "").strip() or None for col in CSV_COLUMNS})
    if not records:
        raise ValueError("CSV contains no valid rows")
    return records


def import_raw(
    title: str,
    company: str,
    location: str | None = None,
    description: str | None = None,
    url: str | None = None,
    posted_at: datetime | None = None,
) -> RawListing:
    """Build a deterministic RawListing for imports (re-imports dedupe)."""
    digest = content_hash(title, company, description)
    return RawListing(
        source="import",
        external_id=f"import-{digest[:16]}",
        title=title,
        company=company,
        location=location,
        description=description,
        url=url,
        posted_at=posted_at,
    )


def build_sources() -> dict[str, ListingSource]:
    """Construct configured source adapters from settings."""
    settings = get_settings()
    limiter = RateLimiter(settings.ingest_min_interval)
    configured: dict[str, ListingSource] = {
        "greenhouse": sources.GreenhouseSource(
            settings.ingest_greenhouse_boards,
            retries=settings.ingest_http_retries,
            backoff=settings.ingest_http_backoff,
            limiter=limiter,
        ),
        "lever": sources.LeverSource(
            settings.ingest_lever_companies,
            retries=settings.ingest_http_retries,
            backoff=settings.ingest_http_backoff,
            limiter=limiter,
        ),
    }
    if settings.ingest_remoteok_enabled:
        configured["remoteok"] = sources.RemoteOKSource(
            retries=settings.ingest_http_retries,
            backoff=settings.ingest_http_backoff,
            limiter=limiter,
        )
    return configured


async def _insert_listing(session: AsyncSession, raw: RawListing) -> str:
    """Insert one listing + skill rows. Returns 'inserted' or 'skipped'."""
    existing = await session.scalar(
        select(Listing.id).where(
            Listing.source == raw.source, Listing.external_id == raw.external_id
        )
    )
    if existing is not None:
        return "skipped"
    digest = content_hash(raw.title, raw.company, raw.description)
    dup = await session.scalar(select(Listing.id).where(Listing.content_hash == digest))
    if dup is not None:
        return "skipped"
    row = Listing(
        source=raw.source,
        external_id=raw.external_id,
        title=raw.title,
        company=raw.company,
        location=raw.location,
        remote=raw.remote,
        salary_min=raw.salary_min,
        salary_max=raw.salary_max,
        currency=raw.currency,
        description=clean_html(raw.description),
        url=raw.url,
        posted_at=raw.posted_at,
        content_hash=digest,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return "skipped"
    try:
        extracted = extract(f"{raw.title}\n{row.description or ''}")
    except ValueError:
        extracted = None
    if extracted is not None:
        for skill in extracted.required:
            session.add(ListingSkill(listing_id=row.id, skill=skill, required=True))
        for skill in extracted.preferred:
            if skill not in extracted.required:
                session.add(ListingSkill(listing_id=row.id, skill=skill, required=False))
        await session.flush()
    return "inserted"


async def run_ingestion(
    source_name: str,
    factory: async_sessionmaker[AsyncSession],
    fetcher: Callable[[], Awaitable[list[RawListing]]] | None = None,
) -> dict[str, int]:
    """Run one ingestion pass for a source; always records an IngestionRun.

    `fetcher` overrides the HTTP fetch (tests inject fakes; production uses
    the configured adapter).
    """
    async with factory() as session:
        return await run_ingestion_in(source_name, session, fetcher)


async def run_ingestion_in(
    source_name: str,
    session: AsyncSession,
    fetcher: Callable[[], Awaitable[list[RawListing]]] | None = None,
    actor: uuid.UUID | None = None,
) -> dict[str, int]:
    """Pipeline body over a caller-managed session (router reuses its own)."""
    stats = {"fetched": 0, "inserted": 0, "skipped": 0, "errors": 0}
    run = IngestionRun(source=source_name)
    session.add(run)
    await session.flush()

    if fetcher is None:
        adapter = build_sources().get(source_name)
        if adapter is None:
            run.finished_at = utcnow()
            run.errors = 1
            run.error_detail = f"unknown source: {source_name}"
            await session.commit()
            return {**stats, "errors": 1}
        fetcher = _http_fetcher(adapter)

    try:
        raws = await fetcher()
    except Exception as exc:
        logger.warning("ingestion fetch failed for %s: %s", source_name, exc)
        run.finished_at = utcnow()
        run.errors = 1
        run.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
        await session.commit()
        return {**stats, "errors": 1}

    stats["fetched"] = len(raws)
    for raw in raws:
        try:
            outcome = await _insert_listing(session, raw)
            stats[outcome] += 1
        except Exception as exc:
            logger.warning("ingestion item failed (%s): %s", raw.external_id, exc)
            await session.rollback()
            stats["errors"] += 1

    run.finished_at = utcnow()
    run.fetched = stats["fetched"]
    run.inserted = stats["inserted"]
    run.skipped = stats["skipped"]
    run.errors = stats["errors"]
    if actor is not None:
        await audit_repository.log(session, actor, "ingestion.import", "listing")
    await session.commit()
    await invalidate_analytics()
    return stats


def _http_fetcher(
    adapter: ListingSource,
) -> Callable[[], Awaitable[list[RawListing]]]:
    """Wrap an adapter's fetch in a fresh HTTP client (production path)."""

    async def _fetch() -> list[RawListing]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await adapter.fetch(client)

    return _fetch


async def auto_match(factory: async_sessionmaker[AsyncSession], limit: int = 500) -> dict[str, int]:
    """Score new listings against every profiled user (idempotent, capped).

    A listing is 'new' for a user when no MatchResult with its id exists yet.
    Returns {users, scored}.
    """
    result = {"users": 0, "scored": 0}
    async with factory() as session:
        profiles = (await session.execute(select(Profile))).scalars().all()
        for profile in profiles:
            if result["scored"] >= limit:
                break
            user = await session.get(User, profile.user_id)
            if user is None:
                continue
            scored_ids = set(
                (
                    await session.execute(
                        select(MatchResult.listing_id).where(
                            MatchResult.user_id == user.id,
                            MatchResult.listing_id.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            stmt = select(Listing).order_by(Listing.created_at.desc())
            if scored_ids:
                stmt = stmt.where(Listing.id.not_in(scored_ids))
            stmt = stmt.limit(limit - result["scored"])
            listings = (await session.execute(stmt)).scalars().all()
            if not listings:
                continue
            result["users"] += 1
            view = match_scorer.profile_view(profile.skills, profile.target_roles)
            weights = match_service.weights_from_settings()
            for listing in listings:
                text = listing.description or listing.title
                try:
                    extracted = extract(f"{listing.title}\n{text}")
                except ValueError:
                    continue
                scored = match_scorer.score_match(view, extracted, listing.title, weights)
                session.add(
                    MatchResult(
                        user_id=user.id,
                        listing_id=listing.id,
                        title=listing.title,
                        score=scored.score,
                        breakdown=dict(scored.breakdown),
                    )
                )
                result["scored"] += 1
            await session.commit()
    if result["scored"]:
        await invalidate_analytics()
    return result
