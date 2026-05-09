from __future__ import annotations

from src.utils.logger import Timer, get_logger as _get_logger
import logging

from neo4j import AsyncGraphDatabase
from fastapi import APIRouter, HTTPException

from graph_store.config import settings
from graph_store.models import GraphIngestRequest, GraphTraverseRequest

logger = _get_logger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


def _fresh_driver():
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
        max_connection_lifetime=300,
        connection_acquisition_timeout=60,
        keep_alive=True,
    )


@router.get("/nodes")
async def graph_nodes(limit: int = 50) -> dict:
    driver = _fresh_driver()
    with Timer() as t:
        try:
            async with driver.session(database=settings.neo4j_database) as session:
                result = await session.run(
                    "MATCH (n) WHERE NOT n:Chunk AND NOT n:Document RETURN labels(n)[0] AS label, n.name AS name LIMIT $limit",
                    limit=limit,
                )
                records = await result.data()
        finally:
            await driver.close()
    logger.info("graph_nodes", extra={"count": len(records), "duration_ms": t.ms})
    return {"count": len(records), "nodes": records}


@router.post("/ingest")
async def graph_ingest(request: GraphIngestRequest) -> dict:
    from ingestion.storage.supabase_store import get_client
    from graph_store.extractor import extract_batch
    from graph_store.writer import ensure_indexes, upsert_chunk

    sb = get_client()
    try:
        result = (
            sb.table("chunks")
            .select("chunk_id, doc_id, text, source, source_type, team_id, chunk_index")
            .in_("chunk_id", request.chunk_ids)
            .eq("team_id", request.team_id)
            .execute()
        )
        rows = result.data or []
    except Exception:
        logger.exception("graph_ingest_supabase_error", extra={"chunk_ids": request.chunk_ids[:5]})
        raise HTTPException(status_code=502, detail="Failed to fetch chunks from Supabase")

    if not rows:
        return {"ingested": 0}

    texts = [r["text"] for r in rows]
    # Run Gemini extraction first (can take minutes) — driver created AFTER this
    extractions = await extract_batch(texts)

    class _ChunkProxy:
        def __init__(self, row: dict) -> None:
            self.chunk_id = row["chunk_id"]
            self.doc_id = row["doc_id"]
            self.text = row["text"]
            self.source = row["source"]
            self.source_type = row["source_type"]
            self.team_id = row["team_id"]
            self.chunk_index = row["chunk_index"]

    # Fresh driver opened AFTER extraction so the connection isn't idle during Gemini calls
    driver = _fresh_driver()
    try:
        await ensure_indexes(driver)
        ingested = 0
        for row, extraction in zip(rows, extractions):
            try:
                await upsert_chunk(_ChunkProxy(row), extraction, driver)
                ingested += 1
            except Exception:
                logger.exception("graph/ingest: upsert failed for chunk_id=%s", row["chunk_id"])
    finally:
        await driver.close()

    logger.info("graph_ingest_done", extra={"ingested": ingested, "total": len(rows)})
    return {"ingested": ingested}


@router.get("/traverse")
async def graph_traverse(type: str, name: str, team_id: str) -> dict:
    from graph_store.reader import (
        find_library_chunks,
        traverse_from_incident,
        traverse_from_service,
    )

    driver = _fresh_driver()
    try:
        if type == "incident":
            texts = await traverse_from_incident(name, team_id, driver)
        elif type == "service":
            texts = await traverse_from_service(name, team_id, driver)
        elif type == "library":
            texts = await find_library_chunks(name, team_id, driver)
        else:
            raise HTTPException(status_code=400, detail="type must be incident, service, or library")
    finally:
        await driver.close()

    return {"type": type, "name": name, "team_id": team_id, "chunks": texts}
