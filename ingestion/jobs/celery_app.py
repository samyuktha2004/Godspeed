"""
Re-export shim — do not add task definitions or beat schedules here.

All Celery configuration lives in src/celery_app.py (the authoritative app).
This file exists so that task modules under ingestion/jobs/ can import
`celery_app` without circular-import issues, and so the worker can be started
with either:

    celery -A src.celery_app worker
    celery -A ingestion.jobs.celery_app worker   # same app, both work
"""

from src.celery_app import app as celery_app  # noqa: F401

__all__ = ["celery_app"]
