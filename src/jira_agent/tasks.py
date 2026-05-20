from __future__ import annotations

import asyncio
import logging

from ingestion.jobs.celery_app import celery_app
from src.jira_agent.config import jira_config

logger = logging.getLogger(__name__)


@celery_app.task(name="jira.process_issue", queue="critical", bind=True, max_retries=3)
def jira_process_issue(self, issue_key: str, team_id: str = "") -> dict:
    """Webhook-triggered single-issue ingestion."""
    try:
        from src.jira_agent.pipeline import ingest_issue
        count = asyncio.run(
            ingest_issue(issue_key, team_id or jira_config.team_id)
        )
        return {"issue_key": issue_key, "chunks_stored": count}
    except Exception as exc:
        logger.exception("jira_process_issue task failed for %s", issue_key)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="jira.sync_project", queue="polling", bind=True, max_retries=2)
def jira_sync_project(self, project_key: str, team_id: str = "") -> dict:
    """Full project sync — intended for manual trigger or scheduled use."""
    try:
        from src.jira_agent.pipeline import ingest_project
        count = asyncio.run(
            ingest_project(project_key, team_id or jira_config.team_id)
        )
        return {"project_key": project_key, "chunks_stored": count}
    except Exception as exc:
        logger.exception("jira_sync_project task failed for %s", project_key)
        raise self.retry(exc=exc, countdown=120)
