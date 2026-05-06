"""Celery task implementations for ingestion, polling, and webhook processing."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task, current_task
from redis import Redis

from src.celery_app import app
from src.config import settings
from src.redis.cache import SyncStateCache, CredentialCache
from src.redis.queues import IngestQueue, Priority
from src.ingestion.orchestrator import IngestionOrchestrator
from src.adapters.web_scraper import WebScraperAdapter, SitemapAdapter, UrlListAdapter
from src.adapters.polling import (
    LogAggregatorAdapter,
    MetricsAdapter,
    ErrorTraceAdapter,
    BusinessDataAdapter,
)

logger = logging.getLogger(__name__)

# Redis client
redis_client = Redis(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db,
    password=settings.redis.password or None,
)


# ====== Polling Tasks ======


@app.task(queue="polling", bind=True, max_retries=3)
def sync_slack_incremental(self):
    """Poll Slack for new messages incrementally."""
    logger.info("Starting Slack incremental sync")

    # Placeholder: would use SlackAdapter
    # For now, just log
    logger.info("Slack sync completed (placeholder)")


@app.task(queue="polling", bind=True, max_retries=3)
def sync_github_incremental(self):
    """Poll GitHub for new events incrementally."""
    logger.info("Starting GitHub incremental sync")

    # Placeholder: would use GitHubAdapter
    logger.info("GitHub sync completed (placeholder)")


@app.task(queue="polling", bind=True, max_retries=3)
def sync_jira_incremental(self):
    """Poll Jira for new issues incrementally."""
    logger.info("Starting Jira incremental sync")

    # Placeholder: would use JiraAdapter
    logger.info("Jira sync completed (placeholder)")


@app.task(queue="polling", bind=True, max_retries=3)
def poll_server_logs(self):
    """Poll and ingest ERROR/WARN logs from monitored services."""
    logger.info("Starting server log polling")

    try:
        adapter = LogAggregatorAdapter()
        sync_state = SyncStateCache(redis_client)

        for service in settings.sync.monitored_services:
            logger.info(f"Polling logs for service: {service}")

            # Get last sync time
            last_sync = sync_state.get_last_sync("logs", service)
            if not last_sync:
                last_sync = datetime.utcnow() - timedelta(minutes=5)

            # Fetch logs
            import asyncio

            docs = asyncio.run(adapter.fetch_incremental(service, last_sync))
            logger.info(f"Fetched {len(docs)} log entries from {service}")

            # Queue for ingestion
            ingest_queue = IngestQueue(redis_client)
            for doc in docs:
                asyncio.run(
                    ingest_queue.add(
                        source_type="log",
                        payload=doc.__dict__,
                        rbac_tags={"service": service},
                        priority=Priority.CRITICAL if doc.priority >= 5 else Priority.HIGH,
                    )
                )

            # Update sync time
            sync_state.set_last_sync("logs", service)

        logger.info("Server log polling completed")

    except Exception as e:
        logger.error(f"Error polling server logs: {e}")
        raise self.retry(exc=e, countdown=60)


@app.task(queue="polling", bind=True, max_retries=3)
def poll_metrics_anomalies(self):
    """Poll metrics for anomalies."""
    logger.info("Starting metrics anomaly polling")

    try:
        adapter = MetricsAdapter()
        sync_state = SyncStateCache(redis_client)

        # Placeholder: would poll actual metrics sources
        logger.info("Metrics anomaly polling completed (placeholder)")

    except Exception as e:
        logger.error(f"Error polling metrics: {e}")
        raise self.retry(exc=e, countdown=60)


@app.task(queue="polling", bind=True, max_retries=3)
def poll_error_traces(self):
    """Poll error traces from APM services."""
    logger.info("Starting error trace polling")

    try:
        adapter = ErrorTraceAdapter()
        sync_state = SyncStateCache(redis_client)

        # Placeholder: would poll actual APM services
        logger.info("Error trace polling completed (placeholder)")

    except Exception as e:
        logger.error(f"Error polling error traces: {e}")
        raise self.retry(exc=e, countdown=60)


# ====== Web Scraping Tasks ======


@app.task(queue="high", bind=True, max_retries=3)
def scrape_url(self, url: str):
    """Scrape a single URL and queue for ingestion."""
    logger.info(f"Starting to scrape URL: {url}")

    try:
        adapter = WebScraperAdapter()
        import asyncio

        doc = asyncio.run(adapter.fetch_url(url))

        if doc:
            logger.info(f"Successfully scraped {url}")

            # Queue for ingestion
            ingest_queue = IngestQueue(redis_client)
            asyncio.run(
                ingest_queue.add(
                    source_type="web",
                    payload=doc.__dict__,
                    rbac_tags={"domain": doc.raw_metadata.get("domain")},
                    priority=Priority.NORMAL,
                )
            )
        else:
            logger.warning(f"Failed to scrape {url}")

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        raise self.retry(exc=e, countdown=60)


@app.task(queue="high", bind=True, max_retries=3)
def scrape_sitemap(self, domain: str):
    """Scrape all URLs from a sitemap."""
    logger.info(f"Starting sitemap crawl for: {domain}")

    try:
        adapter = SitemapAdapter()
        import asyncio

        docs = asyncio.run(adapter.fetch_all(domain))
        logger.info(f"Scraped {len(docs)} pages from sitemap at {domain}")

        # Queue all for ingestion
        ingest_queue = IngestQueue(redis_client)
        for doc in docs:
            asyncio.run(
                ingest_queue.add(
                    source_type="web",
                    payload=doc.__dict__,
                    rbac_tags={"domain": domain},
                    priority=Priority.NORMAL,
                )
            )

    except Exception as e:
        logger.error(f"Error scraping sitemap for {domain}: {e}")
        raise self.retry(exc=e, countdown=60)


# ====== Webhook Processing Tasks ======


@app.task(queue="critical", bind=True, max_retries=5)
def process_webhook_event(self, source_type: str, event_data: dict, rbac_tags: dict):
    """
    Route webhook event to appropriate agent for real-time ingestion.

    Priority: CRITICAL for real-time processing
    """
    logger.info(f"Processing webhook event from {source_type}")

    try:
        # Queue for immediate processing
        ingest_queue = IngestQueue(redis_client)
        import asyncio

        asyncio.run(
            ingest_queue.add(
                source_type=source_type,
                payload=event_data,
                rbac_tags=rbac_tags,
                priority=Priority.CRITICAL,
            )
        )

        logger.info(f"Queued webhook event for {source_type}")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise self.retry(exc=e, countdown=10)


# ====== Enrichment Tasks ======


@app.task(queue="high", bind=True, max_retries=3)
def enrich_and_index_document(self, document: dict):
    """
    Extract entities, relationships, and index document.

    This runs after the document has been parsed and is ready for enrichment.
    """
    logger.info(f"Enriching document: {document.get('uri')}")

    try:
        # Placeholder: would run entity extraction, relationship extraction, etc.
        logger.info(f"Document enrichment completed (placeholder)")

    except Exception as e:
        logger.error(f"Error enriching document: {e}")
        raise self.retry(exc=e, countdown=60)


# ====== Health Check / Monitoring Tasks ======


@app.task(queue="low", bind=True)
def check_queue_health(self):
    """Monitor queue health and log statistics."""
    try:
        ingest_queue = IngestQueue(redis_client)
        stats = ingest_queue.get_stats()

        logger.info(f"Queue stats: {stats}")

    except Exception as e:
        logger.error(f"Error checking queue health: {e}")
