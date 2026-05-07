from __future__ import annotations

import logging

from neo4j import AsyncDriver

from graph_store.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher — traversal queries
# ---------------------------------------------------------------------------

_TRAVERSE_INCIDENT_VIA_LIBRARY = """
MATCH (i:Incident {incident_id: $incident_id})
      -[:CAUSED_BY]->(s:Service)
      -[:DEPENDS_ON]->(l:Library)
      <-[:REFERENCES]-(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_TRAVERSE_INCIDENT_VIA_MENTIONS = """
MATCH (i:Incident {incident_id: $incident_id})
      -[:CAUSED_BY]->(s:Service)
      <-[:MENTIONS]-(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_TRAVERSE_INCIDENT_VIA_DOCS = """
MATCH (i:Incident {incident_id: $incident_id})
      -[:CAUSED_BY]->(s:Service)
      <-[:DOCUMENTS]-(d:Document)
      -[:HAS_CHUNK]->(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_TRAVERSE_SERVICE_MENTIONS = """
MATCH (s:Service {name: $service_name, team_id: $team_id})
      <-[:MENTIONS]-(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_TRAVERSE_SERVICE_VIA_LIBRARY = """
MATCH (s:Service {name: $service_name, team_id: $team_id})
      -[:DEPENDS_ON]->(l:Library)
      <-[:REFERENCES]-(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_TRAVERSE_SERVICE_VIA_DOCS = """
MATCH (s:Service {name: $service_name, team_id: $team_id})
      <-[:DOCUMENTS]-(d:Document)
      -[:HAS_CHUNK]->(c:Chunk {team_id: $team_id})
RETURN DISTINCT c.text AS text
"""

_FIND_LIBRARY_CHUNKS = """
MATCH (l:Library {name: $library_name})
      <-[:REFERENCES]-(c:Chunk {team_id: $team_id})
RETURN c.text AS text
ORDER BY c.chunk_index ASC
"""

_FIND_RELATED_CHUNKS = """
MATCH (start:Chunk {chunk_id: $chunk_id})-[:MENTIONS|REFERENCES]->(pivot)
WITH pivot
MATCH (c:Chunk {team_id: $team_id})-[:MENTIONS|REFERENCES]->(pivot)
WHERE c.chunk_id <> $chunk_id
RETURN DISTINCT c.text AS text
LIMIT 20
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_query(driver: AsyncDriver, cypher: str, **params) -> list[str]:
    async with driver.session(database=settings.neo4j_database) as session:
        result = await session.run(cypher, **params)
        records = await result.data()
        return [r["text"] for r in records if r.get("text")]


async def _union_queries(driver: AsyncDriver, queries: list[tuple[str, dict]]) -> list[str]:
    seen: set[str] = set()
    texts: list[str] = []
    for cypher, params in queries:
        for text in await _run_query(driver, cypher, **params):
            if text not in seen:
                seen.add(text)
                texts.append(text)
    return texts


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

async def traverse_from_incident(
    incident_id: str, team_id: str, driver: AsyncDriver
) -> list[str]:
    return await _union_queries(
        driver,
        [
            (_TRAVERSE_INCIDENT_VIA_LIBRARY,  {"incident_id": incident_id, "team_id": team_id}),
            (_TRAVERSE_INCIDENT_VIA_MENTIONS, {"incident_id": incident_id, "team_id": team_id}),
            (_TRAVERSE_INCIDENT_VIA_DOCS,     {"incident_id": incident_id, "team_id": team_id}),
        ],
    )


async def traverse_from_service(
    service_name: str, team_id: str, driver: AsyncDriver
) -> list[str]:
    return await _union_queries(
        driver,
        [
            (_TRAVERSE_SERVICE_MENTIONS,    {"service_name": service_name, "team_id": team_id}),
            (_TRAVERSE_SERVICE_VIA_LIBRARY, {"service_name": service_name, "team_id": team_id}),
            (_TRAVERSE_SERVICE_VIA_DOCS,    {"service_name": service_name, "team_id": team_id}),
        ],
    )


async def find_library_chunks(
    library_name: str, team_id: str, driver: AsyncDriver
) -> list[str]:
    return await _run_query(
        driver, _FIND_LIBRARY_CHUNKS, library_name=library_name, team_id=team_id
    )


async def find_related_chunks(
    chunk_id: str, team_id: str, driver: AsyncDriver
) -> list[str]:
    return await _run_query(
        driver, _FIND_RELATED_CHUNKS, chunk_id=chunk_id, team_id=team_id
    )
