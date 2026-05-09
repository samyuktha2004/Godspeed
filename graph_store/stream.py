from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from neo4j import AsyncGraphDatabase

from graph_store.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])

_SNAPSHOT_QUERY = """
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


@router.websocket("/graph/stream")
async def graph_stream(websocket: WebSocket):
    await websocket.accept()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
        max_connection_lifetime=1800,
        connection_acquisition_timeout=30,
        keep_alive=True,
        liveness_check_timeout=10,
    )
    try:
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(_SNAPSHOT_QUERY)
            seen_nodes: set[str] = set()
            seen_edges: set[tuple] = set()

            async for record in result:
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
    except Exception:
        logger.exception("graph_stream: error")
        await websocket.send_json({"event": "error", "message": "Graph stream failed"})
    finally:
        await driver.close()
