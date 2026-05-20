from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from ingestion.jobs.celery_app import celery_app
from src.confluence_agent.config import confluence_config

logger = logging.getLogger(__name__)


@celery_app.task(name="confluence.process_page", queue="critical", bind=True, max_retries=3)
def confluence_process_page(self, page_id: str, space_key: str = "", team_id: str = "") -> dict:
    """Webhook-triggered single-page ingestion."""
    try:
        from src.confluence_agent.pipeline import ingest_page
        count = asyncio.run(
            ingest_page(page_id, space_key, team_id or confluence_config.team_id)
        )
        return {"page_id": page_id, "chunks_stored": count}
    except Exception as exc:
        logger.exception("confluence_process_page task failed for %s", page_id)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="confluence.sync_space", queue="polling", bind=True, max_retries=2)
def confluence_sync_space(self, space_key: str, team_id: str = "") -> dict:
    """Full space sync."""
    try:
        from src.confluence_agent.pipeline import ingest_space
        count = asyncio.run(
            ingest_space(space_key, team_id or confluence_config.team_id)
        )
        return {"space_key": space_key, "chunks_stored": count}
    except Exception as exc:
        logger.exception("confluence_sync_space task failed for %s", space_key)
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name="confluence.periodic_sync", queue="polling")
def confluence_periodic_sync() -> dict:
    """Beat task: incremental sync of all configured spaces (60min cadence)."""
    from src.confluence_agent.adapter import ConfluenceAdapter
    from src.confluence_agent.pipeline import ingest_page

    spaces = confluence_config.space_list
    if not spaces:
        logger.info("confluence_periodic_sync: no spaces configured")
        return {"spaces": []}

    since = datetime.utcnow() - timedelta(hours=1)
    results = {}
    adapter = ConfluenceAdapter()

    async def _sync_all():
        total = 0
        for space_key in spaces:
            docs = await adapter.fetch_incremental(space_key, since)
            for raw_doc in docs:
                pid = raw_doc.metadata.get("page_id", "")
                if pid:
                    n = await ingest_page(pid, space_key, confluence_config.team_id)
                    total += n
            results[space_key] = len(docs)
        return total

    total = asyncio.run(_sync_all())
    logger.info("confluence_periodic_sync: synced %d pages, %d total chunks", sum(results.values()), total)
    return {"spaces": results, "total_chunks": total}
