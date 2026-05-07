from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from ingestion.config import settings

celery_app = Celery(
    "ingestion",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "ingestion.jobs.ingest_job",
        "ingestion.jobs.cag_job",
        "src.jira_agent.tasks",
        "src.confluence_agent.tasks",
        "src.file_agent.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=86400,
)

celery_app.conf.beat_schedule = {
    "cag-nightly": {
        "task": "ingestion.jobs.cag_job.run_cag",
        "schedule": crontab(hour=2, minute=0),
    },
    "confluence-periodic-sync": {
        "task": "confluence.periodic_sync",
        "schedule": crontab(minute=0),
    },
}
