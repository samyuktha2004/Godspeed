from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.auth.deps import get_current_user, require_role

from ingestion.models import (
    ConfluenceIngestRequest,
    GithubIngestRequest,
    IngestJobResponse,
    IngestJobStatus,
    IngestSourcePayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Cap PDF uploads — keeps Celery payload sane and prevents memory blowup
_MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB


def _dispatch(payload: IngestSourcePayload) -> IngestJobResponse:
    from ingestion.jobs.ingest_job import run_ingest
    from ingestion.models import IngestJobRecord
    from ingestion.storage.supabase_store import get_client, upsert_job

    task = run_ingest.delay(payload.model_dump())
    job_id = task.id
    logger.info(
        "ingest_dispatch_queued",
        extra={"job_id": job_id, "source_type": payload.source_type, "team_id": payload.team_id},
    )

    record = IngestJobRecord(
        job_id=job_id,
        celery_task_id=task.id,
        status=IngestJobStatus.pending,
        source_type=payload.source_type,
        team_id=payload.team_id,
        created_at=datetime.utcnow(),
    )
    try:
        upsert_job(record, client=get_client())
    except Exception:
        logger.exception("api: failed to persist job record for task %s", job_id)

    return IngestJobResponse(job_id=job_id, status=IngestJobStatus.pending)


@router.post("/confluence", response_model=IngestJobResponse)
async def ingest_confluence(request: ConfluenceIngestRequest, _user: dict = Depends(require_role("admin"))) -> IngestJobResponse:
    logger.info("ingest_confluence_requested", extra={"team_id": request.team_id, "space_key": request.space_key})
    payload = IngestSourcePayload(
        source_type="confluence",
        team_id=request.team_id,
        channel_id=request.channel_id,
        params={"space_key": request.space_key, "page_ids": request.page_ids},
    )
    return _dispatch(payload)


@router.post("/github", response_model=IngestJobResponse)
async def ingest_github(request: GithubIngestRequest, _user: dict = Depends(require_role("admin"))) -> IngestJobResponse:
    logger.info("ingest_github_requested", extra={"team_id": request.team_id, "repo_url": request.repo_url})
    payload = IngestSourcePayload(
        source_type="github",
        team_id=request.team_id,
        channel_id=request.channel_id,
        params={
            "repo_url": request.repo_url,
            "path_filter": request.path_filter,
            "branch": request.branch,
        },
    )
    return _dispatch(payload)


@router.post("/upload", response_model=IngestJobResponse)
async def ingest_pdf(team_id: str, file: UploadFile, channel_id: Optional[str] = None, _user: dict = Depends(require_role("admin"))) -> IngestJobResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds {_MAX_PDF_BYTES // (1024 * 1024)} MB limit",
        )

    # PDF bytes are not JSON-serialisable; store transiently and pass filename+content via task
    # For production, upload to object storage (S3/GCS) and pass the URL instead
    import base64

    payload = IngestSourcePayload(
        source_type="pdf",
        team_id=team_id,
        channel_id=channel_id,
        params={
            "filename": file.filename,
            "content": base64.b64encode(content).decode(),
        },
    )
    logger.info(
        "ingest_pdf_requested",
        extra={"team_id": team_id, "channel_id": channel_id, "filename": file.filename, "size_bytes": len(content)},
    )
    return _dispatch(payload)


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)) -> IngestJobResponse:
    from ingestion.storage.supabase_store import get_job

    record = get_job(job_id)
    if record is None:
        # Fall back to Celery task state if Supabase record not yet written
        from ingestion.jobs.celery_app import celery_app

        task = celery_app.AsyncResult(job_id)
        state_map = {
            "PENDING": IngestJobStatus.pending,
            "STARTED": IngestJobStatus.running,
            "SUCCESS": IngestJobStatus.completed,
            "FAILURE": IngestJobStatus.failed,
        }
        status = state_map.get(task.state, IngestJobStatus.pending)
        logger.info("ingest_job_status_from_celery", extra={"job_id": job_id, "status": str(status)})
        return IngestJobResponse(job_id=job_id, status=status)

    # Tenant isolation: only the owning team (or admins) can see job status
    if user.get("role") not in ("admin", "org_admin"):
        if record.get("team_id") and record.get("team_id") != user.get("team_id"):
            raise HTTPException(status_code=404, detail="Job not found")

    return IngestJobResponse(
        job_id=record["job_id"],
        status=IngestJobStatus(record["status"]),
    )
