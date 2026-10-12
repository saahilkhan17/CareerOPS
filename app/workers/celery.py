"""Celery app: broker/backend from settings, beat schedule for ingestion."""

import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_postrun

from app.core.config import get_settings

logger = logging.getLogger("careerops.worker")

settings = get_settings()

celery = Celery(
    "careerops",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_eager,
    timezone="UTC",
    beat_schedule={
        "ingest-greenhouse-daily": {
            "task": "ingest_source",
            "schedule": crontab(hour=2, minute=0),
            "args": ("greenhouse",),
        },
        "ingest-lever-daily": {
            "task": "ingest_source",
            "schedule": crontab(hour=2, minute=30),
            "args": ("lever",),
        },
        "ingest-remoteok-daily": {
            "task": "ingest_source",
            "schedule": crontab(hour=3, minute=0),
            "args": ("remoteok",),
        },
        "auto-match-nightly": {
            "task": "auto_match",
            "schedule": crontab(hour=4, minute=0),
        },
        "refresh-analytics-weekly": {
            "task": "refresh_analytics",
            "schedule": crontab(hour=1, minute=0, day_of_week="mon"),
        },
    },
)


@task_postrun.connect  # type: ignore[untyped-decorator]
def log_task_outcome(sender: object = None, **kwargs: object) -> None:
    """Structured log for every finished task (PLT-5)."""
    state = kwargs.get("state")
    task_id = kwargs.get("task_id")
    logger.info(
        "task finished",
        extra={
            "task_name": getattr(sender, "name", "?"),
            "task_id": str(task_id),
            "state": str(state),
        },
    )


@task_failure.connect  # type: ignore[untyped-decorator]
def log_task_failure(sender: object = None, **kwargs: object) -> None:
    """Structured log for failed tasks (PLT-5)."""
    task_id = kwargs.get("task_id")
    exc = kwargs.get("exception")
    logger.warning(
        "task failed: %s",
        exc,
        extra={
            "task_name": getattr(sender, "name", "?"),
            "task_id": str(task_id),
        },
    )
