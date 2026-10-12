"""Celery tasks: thin sync wrappers over async ingestion services."""

import asyncio

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.analytics import service as analytics_service
from app.modules.ingestion import service
from app.workers.celery import celery


@celery.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ingest_source",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def ingest_source(self: object, source_name: str) -> dict[str, int]:
    """Fetch → normalize → dedupe → tag one source (idempotent)."""
    return asyncio.run(service.run_ingestion(source_name, get_session_factory()))


@celery.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="auto_match",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def auto_match(self: object) -> dict[str, int]:
    """Score new listings against every profiled user (idempotent, capped)."""
    return asyncio.run(
        service.auto_match(get_session_factory(), limit=get_settings().ingest_automatch_limit)
    )


@celery.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="refresh_analytics",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def refresh_analytics(self: object) -> dict[str, int]:
    """Rebuild the skill summary table + drop cached analytics."""
    refreshed = asyncio.run(analytics_service.refresh_summary(get_session_factory()))
    return {"refreshed": refreshed}
