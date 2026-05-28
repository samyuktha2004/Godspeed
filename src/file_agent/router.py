from __future__ import annotations

from src.utils.logger import get_logger as _get_logger
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.auth.deps import get_current_user
from src.file_agent.config import file_config
from src.file_agent.tasks import file_process_task

logger = _get_logger(__name__)
router = APIRouter(tags=["file"])

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xml", ".txt", ".md",
    ".csv", ".xlsx", ".xls", ".html", ".htm",
}

# Cap single-file uploads — extremely large files OOM the chunker / Celery payload
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _safe_team_id(user: dict, requested_team_id: str) -> str:
    """Pick the user's team unless they're an admin (admins can target any team)."""
    if user.get("role") in ("admin", "org_admin"):
        return requested_team_id or user.get("team_id") or file_config.team_id
    if requested_team_id and requested_team_id != user.get("team_id"):
        raise HTTPException(
            status_code=403,
            detail="Cannot ingest into a team you do not belong to",
        )
    return user.get("team_id") or file_config.team_id


class FolderRequest(BaseModel):
    folder_path: str
    team_id: str = ""


@router.post("/api/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    team_id: str = "",
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a file and dispatch it to the ingestion pipeline."""
    effective_team_id = _safe_team_id(user, team_id)
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        # Stream-copy with explicit size cap
        size_bytes = 0
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MB
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > _MAX_UPLOAD_BYTES:
                tmp.close()
                os.unlink(tmp.name)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                )
            tmp.write(chunk)
        tmp.close()
        size_kb = round(size_bytes / 1024, 1)
        task = file_process_task.delay(tmp.name, effective_team_id)
        logger.info(
            "file_ingest_queued",
            extra={"task_id": task.id, "filename": file.filename, "suffix": suffix, "size_kb": size_kb},
        )
        return {"status": "accepted", "task_id": task.id, "filename": file.filename}
    except HTTPException:
        raise
    except Exception as exc:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/ingest/folder")
async def ingest_folder(
    body: FolderRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Queue ingestion for all supported files in a folder.

    Restricted to admins because it reads from the server filesystem — any
    authenticated user pointing this at /etc would be a path-traversal vector.
    """
    if user.get("role") not in ("admin", "org_admin"):
        raise HTTPException(
            status_code=403,
            detail="Folder ingestion requires an admin role",
        )

    requested = Path(body.folder_path).expanduser().resolve()

    # Constrain folder roots to the configured watch folder. Operators who need
    # to ingest from elsewhere should mount that directory under file_watch_folder.
    allowed_root = Path(file_config.file_watch_folder).expanduser().resolve()
    try:
        requested.relative_to(allowed_root)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"folder_path must be inside the configured watch folder ({allowed_root})",
        )

    if not requested.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder not found: {body.folder_path}")

    team_id = _safe_team_id(user, body.team_id)
    task_ids = []
    for file_path in requested.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            task = file_process_task.delay(str(file_path), team_id)
            task_ids.append({"task_id": task.id, "file": file_path.name})

    logger.info("file_router: queued %d files from folder %s", len(task_ids), str(requested))
    return {"status": "accepted", "tasks": task_ids, "count": len(task_ids)}
