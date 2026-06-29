"""
Authoritative Celery application for Godspeed.

All task modules must register on this app. ingestion/jobs/celery_app.py
re-exports this app so that existing imports keep working — do not create
a second Celery() instance anywhere else.
"""

import logging
import os

from celery import Celery
from kombu import Exchange, Queue
from src.config import settings

logger = logging.getLogger(__name__)

# Create Celery app — single authoritative instance
app = Celery(
    settings.app_name,
    include=[
        "ingestion.jobs.ingest_job",
        "ingestion.jobs.cag_job",
        "src.jira_agent.tasks",
        "src.confluence_agent.tasks",
        "src.file_agent.tasks",
    ],
)

# Configure from settings
app.conf.update(
    broker_url=settings.celery.broker_url,
    result_backend=settings.celery.result_backend,
    task_serializer=settings.celery.task_serializer,
    result_serializer=settings.celery.result_serializer,
    accept_content=settings.celery.accept_content,
    timezone=settings.celery.timezone,
    enable_utc=settings.celery.enable_utc,
    task_track_started=settings.celery.task_track_started,
    task_time_limit=settings.celery.task_time_limit,
    task_soft_time_limit=settings.celery.task_soft_time_limit,
    result_expires=86400,
    # Worker pool: prefork by default; cap concurrency so long-running
    # ingest jobs (GLiNER + BGE-M3 + Neo4j) don't all run on one process.
    worker_concurrency=int(os.environ.get("CELERY_CONCURRENCY", "4")),
    # Prevent one worker from grabbing many tasks at once — keeps the queue
    # balanced across workers and avoids a single worker holding everything
    # when a long job is in flight.
    worker_prefetch_multiplier=1,
    # Acknowledge tasks only after they complete so a worker crash mid-task
    # returns the job to the queue instead of silently losing it.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Define queues with routing
default_exchange = Exchange("tasks", type="direct")

app.conf.task_queues = (
    Queue("critical", exchange=default_exchange, routing_key="tasks.critical", priority=10),
    Queue("high", exchange=default_exchange, routing_key="tasks.high", priority=7),
    Queue("default", exchange=default_exchange, routing_key="tasks.default", priority=5),
    Queue("low", exchange=default_exchange, routing_key="tasks.low", priority=1),
    Queue("webhooks", exchange=default_exchange, routing_key="webhooks", priority=8),
    Queue("polling", exchange=default_exchange, routing_key="polling", priority=3),
)

# Default queue
app.conf.task_default_queue = "default"
app.conf.task_default_exchange_type = "direct"
app.conf.task_default_routing_key = "tasks.default"

# Task routing
app.conf.task_routes = {
    "tasks.ingest.*": {"queue": "critical", "routing_key": "tasks.critical"},
    "tasks.webhooks.*": {"queue": "webhooks", "routing_key": "webhooks"},
    "tasks.polling.*": {"queue": "polling", "routing_key": "polling"},
    "tasks.enrichment.*": {"queue": "high", "routing_key": "tasks.high"},
}


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register periodic tasks with beat scheduler."""

    # Slack polling every 15 minutes
    sender.add_periodic_task(
        settings.sync.slack_poll_interval,
        sync_slack_incremental.s(),
        name="sync-slack-incremental",
    )

    # GitHub polling every 1 hour
    sender.add_periodic_task(
        settings.sync.github_poll_interval,
        sync_github_incremental.s(),
        name="sync-github-incremental",
    )

    # Jira polling every 1 hour
    sender.add_periodic_task(
        settings.sync.jira_poll_interval,
        sync_jira_incremental.s(),
        name="sync-jira-incremental",
    )

    # Log polling every 5 minutes
    sender.add_periodic_task(
        settings.sync.logs_poll_interval,
        poll_server_logs.s(),
        name="poll-server-logs",
    )

    # Metrics polling every 15 minutes
    sender.add_periodic_task(
        settings.sync.metrics_poll_interval,
        poll_metrics_anomalies.s(),
        name="poll-metrics-anomalies",
    )

    # Error traces polling every 10 minutes
    sender.add_periodic_task(
        settings.sync.error_traces_poll_interval,
        poll_error_traces.s(),
        name="poll-error-traces",
    )

    # Staleness scoring daily at 03:00 UTC
    from celery.schedules import crontab
    sender.add_periodic_task(
        crontab(hour=3, minute=0),
        compute_staleness_scores.s(),
        name="compute-staleness-scores",
    )

    # Dependency risk daily at 03:30 UTC
    sender.add_periodic_task(
        crontab(hour=3, minute=30),
        compute_dependency_risk.s(),
        name="compute-dependency-risk",
    )

    # CAG (content-addressed generation) nightly at 02:00 UTC
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        _cag_run_stub.s(),
        name="cag-nightly",
    )

    # Confluence incremental sync — every hour
    sender.add_periodic_task(
        crontab(minute=0),
        _confluence_periodic_sync_stub.s(),
        name="confluence-periodic-sync",
    )

    # New-hire graduation — daily at 01:00 UTC
    sender.add_periodic_task(
        crontab(hour=1, minute=0),
        clear_expired_new_hires.s(),
        name="clear-expired-new-hires",
    )


# Task imports (to be implemented in tasks module)
from celery import shared_task


@shared_task(queue="polling", bind=True, max_retries=3)
def sync_slack_incremental(self):
    """Sync new messages from Slack channels incrementally."""
    pass


@shared_task(queue="polling", bind=True, max_retries=3)
def sync_github_incremental(self):
    """Sync new events from GitHub incrementally."""
    pass


@shared_task(queue="polling", bind=True, max_retries=3)
def sync_jira_incremental(self):
    """Sync new issues from Jira incrementally."""
    pass


@shared_task(queue="polling", bind=True, max_retries=3)
def poll_server_logs(self):
    """Poll and ingest ERROR/WARN logs from monitored services."""
    pass


@shared_task(queue="polling", bind=True, max_retries=3)
def poll_metrics_anomalies(self):
    """Z-score spike detection and escalation trend detection — runs every 15 min."""
    try:
        from src.anomaly.tasks import run_zscore_anomaly_detection
        run_zscore_anomaly_detection()
    except Exception as exc:
        logger.error("poll_metrics_anomalies failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task(queue="polling", bind=True, max_retries=3)
def poll_error_traces(self):
    """Poll error traces from APM services."""
    pass


@shared_task(queue="critical", bind=True, max_retries=5)
def process_webhook_event(self, source_type: str, event_data: dict, rbac_tags: dict):
    """Route webhook event to appropriate agent for real-time ingestion."""
    pass


@shared_task(queue="high", bind=True, max_retries=3)
def enrich_and_index_document(self, document: dict):
    """Extract entities, relationships, and index document."""
    pass


@shared_task(queue="low", bind=True, max_retries=2)
def compute_staleness_scores(self):
    """Daily staleness risk scoring for all documents (03:00 UTC)."""
    try:
        from src.anomaly.tasks import run_staleness_scoring
        run_staleness_scoring()
    except Exception as exc:
        logger.error("compute_staleness_scores failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(queue="low", bind=True, max_retries=2)
def compute_dependency_risk(self):
    """Daily dependency risk modelling from Neo4j graph (03:30 UTC)."""
    try:
        from src.anomaly.tasks import run_dependency_risk_modeling
        run_dependency_risk_modeling()
    except Exception as exc:
        logger.error("compute_dependency_risk failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(queue="low", bind=True, max_retries=2)
def _cag_run_stub(self):
    """Beat entry-point — delegates to the real CAG task in ingestion.jobs.cag_job."""
    try:
        from ingestion.jobs.cag_job import run_cag
        run_cag.delay()
    except Exception as exc:
        logger.error("_cag_run_stub failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(queue="polling", bind=True, max_retries=2)
def _confluence_periodic_sync_stub(self):
    """Beat entry-point — delegates to the real periodic sync task."""
    try:
        from src.confluence_agent.tasks import confluence_periodic_sync
        confluence_periodic_sync.delay()
    except Exception as exc:
        logger.error("_confluence_periodic_sync_stub failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task(queue="low", bind=True, max_retries=2)
def clear_expired_new_hires(self):
    """Daily job to clear is_new_hire=True for users whose new_hire_until date has passed (01:00 UTC)."""
    try:
        from datetime import date
        from src.auth.db import _client as _sb_client

        today = date.today().isoformat()
        sb    = _sb_client()
        result = (
            sb.table("users")
            .update({"is_new_hire": False})
            .eq("is_new_hire", True)
            .lt("new_hire_until", today)
            .execute()
        )
        count = len(result.data) if result.data else 0
        logger.info("clear_expired_new_hires: graduated %d user(s)", count)
    except Exception as exc:
        logger.error("clear_expired_new_hires failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


if __name__ == "__main__":
    app.start()
