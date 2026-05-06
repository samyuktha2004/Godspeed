from __future__ import annotations

import logging

from ingestion.pipeline.embedder import embed_chunks
from ingestion.pipeline.pii_masker import mask_chunks
from ingestion.storage.qdrant_store import delete_chunks_for_doc, upsert_chunks
from src.confluence_agent.adapter import ConfluenceAdapter
from src.confluence_agent.chunker import chunk_confluence_page
from src.confluence_agent.config import confluence_config

logger = logging.getLogger(__name__)


async def ingest_page(page_id: str, space_key: str = "", team_id: str = "") -> int:
    team_id = team_id or confluence_config.team_id
    adapter = ConfluenceAdapter(team_id=team_id)

    raw_doc = await adapter.fetch_page(page_id)
    if raw_doc is None:
        logger.warning("confluence_pipeline: no document returned for page %s", page_id)
        return 0

    chunks = chunk_confluence_page(raw_doc)
    if not chunks:
        logger.warning("confluence_pipeline: no chunks for page %s", page_id)
        return 0

    texts = [c.text for c in chunks]
    masked = mask_chunks(texts)
    for chunk, m in zip(chunks, masked):
        chunk.text = m

    embedded = embed_chunks(chunks)
    delete_chunks_for_doc(raw_doc.doc_id)
    upsert_chunks(embedded)

    logger.info("confluence_pipeline: stored %d chunks for page %s", len(embedded), page_id)
    return len(embedded)


async def ingest_space(space_key: str, team_id: str = "") -> int:
    team_id = team_id or confluence_config.team_id
    adapter = ConfluenceAdapter(team_id=team_id)
    docs = await adapter.fetch_space(space_key)
    total = 0
    for raw_doc in docs:
        pid = raw_doc.metadata.get("page_id", "?")
        chunks = chunk_confluence_page(raw_doc)
        if not chunks:
            continue
        texts = [c.text for c in chunks]
        masked = mask_chunks(texts)
        for chunk, m in zip(chunks, masked):
            chunk.text = m
        embedded = embed_chunks(chunks)
        delete_chunks_for_doc(raw_doc.doc_id)
        upsert_chunks(embedded)
        total += len(embedded)
        logger.info("confluence_pipeline: stored %d chunks for page %s", len(embedded), pid)

    logger.info("confluence_pipeline: space %s sync done — %d total chunks", space_key, total)
    return total
