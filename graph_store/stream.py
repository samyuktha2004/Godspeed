from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from neo4j import AsyncGraphDatabase

from graph_store.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])

# After a DNS/connection failure, skip Neo4j for this many seconds before retrying
_NEO4J_COOLDOWN_S = 120
_neo4j_failed_at: float | None = None


def _neo4j_is_available() -> bool:
    global _neo4j_failed_at
    if _neo4j_failed_at is None:
        return True
    if time.monotonic() - _neo4j_failed_at > _NEO4J_COOLDOWN_S:
        _neo4j_failed_at = None
        return True
    return False


def _mark_neo4j_failed() -> None:
    global _neo4j_failed_at
    if _neo4j_failed_at is None:
        logger.warning(
            "graph_stream: Neo4j unreachable (%s) — graph panel disabled for %ds",
            settings.neo4j_uri,
            _NEO4J_COOLDOWN_S,
        )
    _neo4j_failed_at = time.monotonic()

# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

_SNAPSHOT_QUERY_UNFILTERED = """
MATCH (n)
WHERE NOT n:Chunk AND NOT n:Document AND n.name IS NOT NULL
WITH n
OPTIONAL MATCH (n)-[r]->(m)
WHERE NOT m:Chunk AND NOT m:Document AND m.name IS NOT NULL
RETURN
  labels(n)[0]  AS from_label,
  n.name        AS from_name,
  type(r)       AS rel_type,
  labels(m)[0]  AS to_label,
  m.name        AS to_name
ORDER BY from_name
"""

_SNAPSHOT_QUERY_FILTERED = """
MATCH (n)
WHERE NOT n:Chunk AND NOT n:Document AND n.name IS NOT NULL
WITH n
MATCH (n)<-[:MENTIONS|REFERENCES|HAS_CHUNK]-(c:Chunk)
WHERE c.channel_id IN $channel_ids OR c.channel_id IS NULL
WITH DISTINCT n
OPTIONAL MATCH (n)-[r]->(m)
WHERE NOT m:Chunk AND NOT m:Document AND m.name IS NOT NULL
  AND EXISTS {
    MATCH (m)<-[:MENTIONS|REFERENCES|HAS_CHUNK]-(c2:Chunk)
    WHERE c2.channel_id IN $channel_ids OR c2.channel_id IS NULL
  }
RETURN
  labels(n)[0]  AS from_label,
  n.name        AS from_name,
  type(r)       AS rel_type,
  labels(m)[0]  AS to_label,
  m.name        AS to_name
ORDER BY from_name
"""


# ---------------------------------------------------------------------------
# Session helper — resolve gs_session cookie via Redis
# ---------------------------------------------------------------------------

def _parse_session_cookie(websocket: WebSocket) -> str | None:
    """Extract the gs_session value from the WebSocket cookie header."""
    # FastAPI/Starlette populates websocket.cookies from the Cookie header
    session_id = websocket.cookies.get("gs_session")
    if session_id:
        return session_id
    # Fallback: parse the raw Cookie header manually
    cookie_header = websocket.headers.get("cookie", "")
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("gs_session="):
            return part[len("gs_session="):]
    return None


async def _resolve_session(websocket: WebSocket) -> dict | None:
    """Return the user dict from the gs_session cookie, or None if invalid."""
    from src.auth.router import _get_session

    session_id = _parse_session_cookie(websocket)
    if not session_id:
        return None
    try:
        session = await _get_session(session_id)
        return session.get("user") if session else None
    except Exception as exc:
        logger.warning("graph_stream: session resolution failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

@router.websocket("/graph/stream")
async def graph_stream(websocket: WebSocket):
    await websocket.accept()

    user = await _resolve_session(websocket)
    if not user:
        try:
            await websocket.close(code=4001, reason="Not authenticated")
        except Exception:
            pass
        return

    allowed_channel_ids: list[str] = user.get("allowed_channel_ids") or []
    if not isinstance(allowed_channel_ids, list):
        allowed_channel_ids = []

    use_filtered = bool(allowed_channel_ids)
    if use_filtered:
        logger.info(
            "graph_stream: RBAC active — filtering to %d channel(s) for user %s",
            len(allowed_channel_ids),
            user.get("id"),
        )
    else:
        logger.info("graph_stream: no channel restriction for user %s", user.get("id"))

    if not _neo4j_is_available():
        try:
            await websocket.send_json({"event": "error", "message": "Knowledge graph unavailable"})
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
        return

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
        max_connection_lifetime=300,
        connection_acquisition_timeout=10,
        keep_alive=True,
    )
    try:
        async with driver.session(database=settings.neo4j_database) as session:
            if use_filtered:
                result = await session.run(
                    _SNAPSHOT_QUERY_FILTERED, {"channel_ids": allowed_channel_ids}
                )
            else:
                result = await session.run(_SNAPSHOT_QUERY_UNFILTERED, {})
            records = await result.data()

        seen_nodes: set[str] = set()
        seen_edges: set[tuple] = set()

        for record in records:
            from_label = record["from_label"]
            from_name = record["from_name"]
            rel_type = record["rel_type"]
            to_label = record["to_label"]
            to_name = record["to_name"]

            if from_name and from_name not in seen_nodes:
                seen_nodes.add(from_name)
                await websocket.send_json({
                    "event": "node",
                    "id": from_name,
                    "label": from_label,
                    "name": from_name,
                })
                await asyncio.sleep(0.05)

            if to_name and to_name not in seen_nodes:
                seen_nodes.add(to_name)
                await websocket.send_json({
                    "event": "node",
                    "id": to_name,
                    "label": to_label,
                    "name": to_name,
                })
                await asyncio.sleep(0.05)

            if rel_type and to_name:
                edge_key = (from_name, rel_type, to_name)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    await websocket.send_json({
                        "event": "edge",
                        "from": from_name,
                        "to": to_name,
                        "rel": rel_type,
                    })
                    await asyncio.sleep(0.05)

        await websocket.send_json({"event": "done", "nodes": len(seen_nodes), "edges": len(seen_edges)})

    except WebSocketDisconnect:
        logger.info("graph_stream: client disconnected")
    except Exception as exc:
        _mark_neo4j_failed()
        try:
            await websocket.send_json({"event": "error", "message": "Knowledge graph unavailable"})
        except Exception:
            pass
    finally:
        try:
            await driver.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
