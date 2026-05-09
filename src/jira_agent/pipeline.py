from __future__ import annotations

import logging

from ingestion.pipeline.embedder import embed_chunks
from ingestion.pipeline.pii_masker import mask_chunks
from ingestion.storage import supabase_store
from ingestion.storage.qdrant_store import delete_chunks_for_doc, upsert_chunks
from src.jira_agent.adapter import JiraAdapter
from src.jira_agent.chunker import chunk_jira_issue
from src.jira_agent.config import jira_config

logger = logging.getLogger(__name__)


def _store(raw_doc, embedded):
    supabase_store.upsert_document(raw_doc)
    supabase_store.delete_chunks_for_doc(raw_doc.doc_id)
    supabase_store.upsert_chunks(embedded)
    delete_chunks_for_doc(raw_doc.doc_id)
    upsert_chunks(embedded)


async def ingest_issue(issue_key: str, team_id: str = "") -> int:
    team_id = team_id or jira_config.team_id
    adapter = JiraAdapter(team_id=team_id)

    raw_doc = await adapter.fetch_issue(issue_key)
    if raw_doc is None:
        logger.warning("jira_pipeline: no document returned for %s", issue_key)
        return 0

    chunks = chunk_jira_issue(raw_doc)
    if not chunks:
        logger.warning("jira_pipeline: no chunks produced for %s", issue_key)
        return 0

    texts = [c.text for c in chunks]
    masked_texts = mask_chunks(texts)
    for chunk, masked in zip(chunks, masked_texts):
        chunk.text = masked

    embedded = embed_chunks(chunks)
    _store(raw_doc, embedded)

    logger.info("jira_pipeline: stored %d chunks for %s", len(embedded), issue_key)
    return len(embedded)


async def ingest_project(project_key: str, team_id: str = "") -> int:
    team_id = team_id or jira_config.team_id
    adapter = JiraAdapter(team_id=team_id)
    docs = await adapter.fetch_all(project_key)
    total = 0
    for raw_doc in docs:
        key = raw_doc.metadata.get("issue_key", "?")
        chunks = chunk_jira_issue(raw_doc)
        if not chunks:
            continue
        texts = [c.text for c in chunks]
        masked_texts = mask_chunks(texts)
        for chunk, masked in zip(chunks, masked_texts):
            chunk.text = masked
        embedded = embed_chunks(chunks)
        _store(raw_doc, embedded)
        total += len(embedded)
        logger.info("jira_pipeline: stored %d chunks for %s", len(embedded), key)

    logger.info("jira_pipeline: project %s sync complete — %d total chunks", project_key, total)
    return total
