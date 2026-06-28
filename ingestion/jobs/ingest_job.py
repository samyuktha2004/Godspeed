from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from celery import Task

from ingestion.jobs.celery_app import celery_app
from ingestion.models import IngestJobRecord, IngestJobStatus, IngestSourcePayload

logger = logging.getLogger(__name__)

_SOURCE_REGISTRY: dict[str, Any] = {}


async def _run_graph_pipeline(embedded, doc) -> None:
    try:
        from graph_store.config import settings as graph_settings
    except Exception:
        logger.warning("ingest_job: graph_store not available — skipping graph pipeline")
        return

    if not graph_settings.neo4j_uri:
        logger.warning("ingest_job: NEO4J_URI not set — skipping graph pipeline")
        return
    try:
        from graph_store.pipeline import run_graph_pipeline
        from graph_store.writer import get_driver
        await run_graph_pipeline(embedded, doc, get_driver())
    except Exception:
        logger.exception(
            "ingest_job: graph pipeline failed for doc_id=%s — continuing without graph", doc.doc_id
        )


def _get_source_registry() -> dict[str, Any]:
    if not _SOURCE_REGISTRY:
        from ingestion.sources.confluence import ConfluenceSource
        from ingestion.sources.github import GithubSource
        from ingestion.sources.jira import JiraSource
        from ingestion.sources.pdf import PDFSource

        _SOURCE_REGISTRY.update(
            {
                "confluence": ConfluenceSource,
                "github": GithubSource,
                "pdf": PDFSource,
                "jira": JiraSource,
            }
        )
    return _SOURCE_REGISTRY


@celery_app.task(bind=True, name="ingestion.jobs.ingest_job.run_ingest", max_retries=2)
def run_ingest(self: Task, payload: dict[str, Any]) -> dict[str, Any]:
    job_id = self.request.id
    return asyncio.run(_run_ingest_async(job_id, IngestSourcePayload(**payload)))


async def _run_ingest_async(job_id: str, payload: IngestSourcePayload) -> dict[str, Any]:
    from ingestion.config import settings
    from ingestion.pipeline.chunker import chunk_document
    from ingestion.pipeline.embedder import embed_chunks
    from ingestion.pipeline.pii_masker import mask_pii
    from ingestion.storage.bm25_store import rebuild_from_supabase
    from ingestion.storage.qdrant_store import delete_chunks_for_doc, upsert_chunks as qdrant_upsert
    from ingestion.storage.supabase_store import (
        delete_chunks_for_doc as sb_delete_chunks,
        get_client,
        upsert_chunks as sb_upsert_chunks,
        upsert_document,
        upsert_job,
    )

    sb = get_client()
    job = IngestJobRecord(
        job_id=job_id,
        celery_task_id=job_id,
        status=IngestJobStatus.running,
        source_type=payload.source_type,
        team_id=payload.team_id,
    )
    upsert_job(job, client=sb)

    total_chunks = 0

    try:
        registry = _get_source_registry()
        source_cls = registry.get(payload.source_type)
        if source_cls is None:
            raise ValueError(f"Unknown source type: {payload.source_type}")

        if payload.source_type == "github":
            # GithubSource requires supabase_client for SHA change-detection
            source = source_cls(team_id=payload.team_id, supabase_client=sb, **payload.params)
        elif payload.source_type == "pdf":
            # content arrives as base64 string because Celery serialises to JSON
            import base64
            params = dict(payload.params)
            if isinstance(params.get("content"), str):
                params["content"] = base64.b64decode(params["content"])
            source = source_cls(team_id=payload.team_id, **params)
        else:
            source = source_cls(team_id=payload.team_id, **payload.params)

        raw_docs = await source.fetch()
        logger.info("ingest_job: fetched %d documents from %s", len(raw_docs), payload.source_type)

        for doc in raw_docs:
            # Stamp channel_id from the payload if the source didn't set it
            if doc.channel_id is None and payload.channel_id is not None:
                doc.channel_id = payload.channel_id

            # Delete stale vectors and chunk records before re-ingesting the same document
            delete_chunks_for_doc(doc.doc_id)
            sb_delete_chunks(doc.doc_id, client=sb)

            chunks = chunk_document(doc)
            if not chunks:
                logger.warning("ingest_job: no chunks produced for doc_id=%s", doc.doc_id)
                continue

            # Propagate channel_id from doc down to every chunk
            for c in chunks:
                if c.channel_id is None:
                    c.channel_id = doc.channel_id

            # Mask PII in chunk text before embedding or storing
            for chunk in chunks:
                chunk.text = mask_pii(chunk.text)

            upsert_document(doc, client=sb)
            embedded = embed_chunks(chunks)
            qdrant_upsert(embedded)
            sb_upsert_chunks(chunks, client=sb)
            total_chunks += len(chunks)
            logger.info("ingest_job: ingested %d chunks for doc_id=%s", len(chunks), doc.doc_id)

            await _run_graph_pipeline(embedded, doc)

        # BM25 is opt-in (settings.enable_bm25). Default OFF: skip the full
        # rebuild_from_supabase() that re-reads/re-tokenizes the entire corpus on
        # every ingest. Default retrieval uses Qdrant dense + sparse instead.
        if settings.enable_bm25:
            rebuild_from_supabase()

        # Refresh the routing manifest structure (counts + spaces/repos/projects)
        # so the query-time router sees the new content. Cheap, no LLM — gists are
        # refreshed nightly by the CAG job. Never let this fail the ingest.
        try:
            from ingestion.storage.manifest_store import refresh_manifest_structure
            refresh_manifest_structure(payload.team_id, client=sb)
        except Exception:
            logger.warning("ingest_job: routing manifest refresh failed for team %s", payload.team_id)

        job.status = IngestJobStatus.completed
        job.completed_at = datetime.utcnow()
        job.chunks_ingested = total_chunks

    except Exception as exc:
        logger.exception("ingest_job: job %s failed", job_id)
        job.status = IngestJobStatus.failed
        job.completed_at = datetime.utcnow()
        job.error = str(exc)

    upsert_job(job, client=sb)

    # Reflect run outcome back to the admin dashboard source list in Redis
    try:
        from src.admin.router import update_source_sync_status
        await update_source_sync_status(
            payload.source_type,
            "ok" if job.status == IngestJobStatus.completed else "error",
            error_msg=job.error,
        )
    except Exception:
        logger.warning("ingest_job: failed to update source sync_status")

    return {"job_id": job_id, "status": job.status.value, "chunks_ingested": total_chunks}
