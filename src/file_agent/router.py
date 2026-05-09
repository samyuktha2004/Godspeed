from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.file_agent.config import file_config
from src.file_agent.tasks import file_process_task

logger = logging.getLogger(__name__)
router = APIRouter(tags=["file"])

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xml", ".txt", ".md",
    ".csv", ".xlsx", ".xls", ".html", ".htm",
}


class FolderRequest(BaseModel):
    folder_path: str
    team_id: str = ""


@router.post("/api/ingest/file")
async def ingest_file(
    file: UploadFile = File(...),
    team_id: str = "",
) -> dict[str, Any]:
    """Upload a file and dispatch it to the ingestion pipeline."""
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.close()
        task = file_process_task.delay(tmp.name, team_id or file_config.team_id)
        logger.info("file_router: queued task %s for uploaded file %s", task.id, file.filename)
        return {"status": "accepted", "task_id": task.id, "filename": file.filename}
    except Exception as exc:
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/ingest/folder")
async def ingest_folder(body: FolderRequest) -> dict[str, Any]:
    """Queue ingestion for all supported files in a folder."""
    folder = Path(body.folder_path)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder not found: {body.folder_path}")

    team_id = body.team_id or file_config.team_id
    task_ids = []
    for file_path in folder.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            task = file_process_task.delay(str(file_path), team_id)
            task_ids.append({"task_id": task.id, "file": file_path.name})

    logger.info("file_router: queued %d files from folder %s", len(task_ids), body.folder_path)
    return {"status": "accepted", "tasks": task_ids, "count": len(task_ids)}
