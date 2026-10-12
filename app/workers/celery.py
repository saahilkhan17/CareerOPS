"""Celery app: broker/backend from settings, beat schedule for ingestion."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

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
    },
)
