from __future__ import annotations

import logging

from neo4j import AsyncDriver

from graph_store.extractor import extract_batch
from graph_store.writer import ensure_indexes, upsert_chunk, upsert_document

logger = logging.getLogger(__name__)


async def run_graph_pipeline(chunks, doc, driver: AsyncDriver) -> None:
    try:
        await ensure_indexes(driver)
        await upsert_document(doc, driver)
    except Exception:
        logger.exception("graph_pipeline: setup failed for doc_id=%s", doc.doc_id)
        return

    texts = [c.text for c in chunks]
    try:
        extractions = await extract_batch(texts)
    except Exception:
        logger.exception("graph_pipeline: extraction failed for doc_id=%s", doc.doc_id)
        return

    total_entities = 0
    total_relationships = 0

    for chunk, extraction in zip(chunks, extractions):
        try:
            await upsert_chunk(chunk, extraction, driver)
            total_entities += len(extraction.entities)
            total_relationships += len(extraction.relationships)
        except Exception:
            logger.exception(
                "graph_pipeline: upsert failed for chunk_id=%s", chunk.chunk_id
            )

    logger.info(
        "graph_pipeline: doc_id=%s — %d chunks, %d entities, %d relationships written",
        doc.doc_id,
        len(chunks),
        total_entities,
        total_relationships,
    )
