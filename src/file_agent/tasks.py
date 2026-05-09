from __future__ import annotations

import logging

from ingestion.jobs.celery_app import celery_app
from src.file_agent.config import file_config

logger = logging.getLogger(__name__)


@celery_app.task(name="file.process_task", queue="default", bind=True, max_retries=3)
def file_process_task(self, file_path: str, team_id: str = "") -> dict:
    try:
        from src.file_agent.pipeline import process_file
        count = process_file(file_path, team_id or file_config.team_id)
        return {"file_path": file_path, "chunks_stored": count}
    except Exception as exc:
        logger.exception("file_process_task failed for %s", file_path)
        raise self.retry(exc=exc, countdown=30)
