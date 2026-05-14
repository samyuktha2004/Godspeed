from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RawDocument(BaseModel):
    doc_id: str
    title: str
    content: str
    source_url: str
    source_type: str
    team_id: str
    channel_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    source: str
    source_type: str
    team_id: str
    chunk_index: int
    channel_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    source: str
    source_type: str
    team_id: str
    chunk_index: int
    channel_id: Optional[str] = None
    dense_vector: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class IngestJobRecord(BaseModel):
    job_id: str
    celery_task_id: str
    status: IngestJobStatus
    source_type: str
    team_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    chunks_ingested: int = 0


class IngestSourcePayload(BaseModel):
    source_type: Literal["confluence", "github", "pdf", "jira"]
    team_id: str
    channel_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)


class ConfluenceIngestRequest(BaseModel):
    space_key: str
    team_id: str
    channel_id: Optional[str] = None
    page_ids: Optional[list[str]] = None


class GithubIngestRequest(BaseModel):
    repo_url: str
    team_id: str
    channel_id: Optional[str] = None
    path_filter: str = "docs/"
    branch: str = "main"


class IngestJobResponse(BaseModel):
    job_id: str
    status: IngestJobStatus
