from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from supabase import Client, create_client

from ingestion.config import settings
from ingestion.models import DocumentChunk, IngestJobRecord, IngestJobStatus, RawDocument

logger = logging.getLogger(__name__)


def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)


def upsert_document(doc: RawDocument, client: Optional[Client] = None) -> None:
    sb = client or get_client()
    try:
        sb.table("documents").upsert(
            {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "source_url": doc.source_url,
                "source_type": doc.source_type,
                "team_id": doc.team_id,
                "channel_id": doc.channel_id,
                "metadata": doc.metadata,
                "last_commit_sha": doc.metadata.get("last_commit_sha"),
                "updated_at": datetime.utcnow().isoformat(),
            },
            on_conflict="doc_id",
        ).execute()
    except Exception:
        logger.exception("supabase_store: failed to upsert document %s", doc.doc_id)
        raise


def upsert_chunks(chunks: list[DocumentChunk], client: Optional[Client] = None) -> None:
    if not chunks:
        return
    sb = client or get_client()
    try:
        rows = [
            {
                "chunk_id": c.chunk_id,
                "qdrant_id": c.chunk_id,
                "doc_id": c.doc_id,
                "text": c.text,
                "source": c.source,
                "source_type": c.source_type,
                "team_id": c.team_id,
                "chunk_index": c.chunk_index,
                "channel_id": c.channel_id,
            }
            for c in chunks
        ]
        sb.table("chunks").upsert(rows, on_conflict="chunk_id").execute()
        logger.info("supabase_store: upserted %d chunks", len(rows))
    except Exception:
        logger.exception("supabase_store: failed to upsert chunks")
        raise


def delete_chunks_for_doc(doc_id: str, client: Optional[Client] = None) -> None:
    sb = client or get_client()
    try:
        sb.table("chunks").delete().eq("doc_id", doc_id).execute()
    except Exception:
        logger.exception("supabase_store: failed to delete chunks for doc_id=%s", doc_id)
        raise


def upsert_job(record: IngestJobRecord, client: Optional[Client] = None) -> None:
    sb = client or get_client()
    try:
        sb.table("ingest_jobs").upsert(
            {
                "job_id": record.job_id,
                "celery_task_id": record.celery_task_id,
                "status": record.status.value,
                "source_type": record.source_type,
                "team_id": record.team_id,
                "created_at": record.created_at.isoformat(),
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "error": record.error,
                "chunks_ingested": record.chunks_ingested,
            },
            on_conflict="job_id",
        ).execute()
    except Exception:
        logger.exception("supabase_store: failed to upsert job %s", record.job_id)


def get_job(job_id: str, client: Optional[Client] = None) -> Optional[dict[str, Any]]:
    sb = client or get_client()
    try:
        result = sb.table("ingest_jobs").select("*").eq("job_id", job_id).maybe_single().execute()
        return result.data
    except Exception:
        logger.exception("supabase_store: failed to get job %s", job_id)
        return None


def get_all_teams(client: Optional[Client] = None) -> list[dict[str, Any]]:
    sb = client or get_client()
    try:
        result = sb.table("teams").select("team_id").execute()
        return result.data or []
    except Exception:
        logger.exception("supabase_store: failed to fetch teams")
        return []


def update_cag_snapshot(team_id: str, snapshot: str, client: Optional[Client] = None) -> None:
    sb = client or get_client()
    try:
        sb.table("teams").upsert(
            {
                "team_id": team_id,
                "cag_snapshot": snapshot,
                "snapshot_at": datetime.utcnow().isoformat(),
            },
            on_conflict="team_id",
        ).execute()
        logger.info("supabase_store: updated CAG snapshot for team %s", team_id)
    except Exception:
        logger.exception("supabase_store: failed to update CAG snapshot for team %s", team_id)
        raise


def get_all_chunks(client: Optional[Client] = None) -> list[dict[str, Any]]:
    sb = client or get_client()
    try:
        result = sb.table("chunks").select("chunk_id, text").execute()
        return result.data or []
    except Exception:
        logger.exception("supabase_store: failed to fetch all chunks")
        return []
