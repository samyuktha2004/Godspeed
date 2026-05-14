from __future__ import annotations

import logging
from typing import Optional

from neo4j import AsyncDriver, AsyncGraphDatabase

from graph_store.config import settings
from graph_store.models import ExtractionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher — indexes
# ---------------------------------------------------------------------------

_IDX_CHUNK = "CREATE INDEX chunk_chunk_id IF NOT EXISTS FOR (n:Chunk) ON (n.chunk_id)"
_IDX_DOCUMENT = "CREATE INDEX document_doc_id IF NOT EXISTS FOR (n:Document) ON (n.doc_id)"
_IDX_SERVICE = "CREATE INDEX service_name_team IF NOT EXISTS FOR (n:Service) ON (n.name, n.team_id)"
_IDX_LIBRARY = "CREATE INDEX library_name IF NOT EXISTS FOR (n:Library) ON (n.name)"
_IDX_INCIDENT = "CREATE INDEX incident_id IF NOT EXISTS FOR (n:Incident) ON (n.incident_id)"
_IDX_TEAM = "CREATE INDEX team_team_id IF NOT EXISTS FOR (n:Team) ON (n.team_id)"

# ---------------------------------------------------------------------------
# Cypher — document + chunk upsert
# ---------------------------------------------------------------------------

_MERGE_DOCUMENT = """
MERGE (d:Document {doc_id: $doc_id})
SET d.title      = $title,
    d.source     = $source,
    d.source_type = $source_type,
    d.team_id    = $team_id
"""

_MERGE_CHUNK = """
MERGE (c:Chunk {chunk_id: $chunk_id})
SET c.qdrant_id   = $qdrant_id,
    c.text        = $text,
    c.source      = $source,
    c.source_type = $source_type,
    c.team_id     = $team_id,
    c.chunk_index = $chunk_index,
    c.channel_id  = $channel_id
"""

_MERGE_HAS_CHUNK = """
MATCH (d:Document {doc_id: $doc_id})
MATCH (c:Chunk    {chunk_id: $chunk_id})
MERGE (d)-[:HAS_CHUNK]->(c)
"""

# ---------------------------------------------------------------------------
# Cypher — entity upsert per label
# ---------------------------------------------------------------------------

_MERGE_SERVICE = """
MERGE (n:Service {name: $name, team_id: $team_id})
"""

_MERGE_LIBRARY = """
MERGE (n:Library {name: $name})
ON CREATE SET n.version = $version
ON MATCH  SET n.version = COALESCE($version, n.version)
"""

_MERGE_INCIDENT = """
MERGE (n:Incident {incident_id: $name})
ON CREATE SET n.title = $name, n.team_id = $team_id, n.status = 'unknown'
"""

_MERGE_TEAM = """
MERGE (n:Team {team_id: $name})
ON CREATE SET n.name = $name
"""

# ---------------------------------------------------------------------------
# Validation sets — labels/rel_types are injected into Cypher strings,
# so we whitelist them before interpolation to prevent injection.
# ---------------------------------------------------------------------------

_VALID_LABELS = frozenset({"Service", "Library", "Incident", "Team", "Chunk", "Document"})
_VALID_REL_TYPES = frozenset(
    {"MENTIONS", "REFERENCES", "DEPENDS_ON", "OWNED_BY", "CAUSED_BY", "DOCUMENTS", "HAS_CHUNK"}
)

# The property name used as the primary merge key for each label,
# and the Python-side parameter name that holds that value.
_LABEL_ID_PROP = {
    "Service":  "name",
    "Library":  "name",
    "Incident": "incident_id",
    "Team":     "team_id",
    "Chunk":    "chunk_id",
    "Document": "doc_id",
}

# ---------------------------------------------------------------------------
# Singleton driver
# ---------------------------------------------------------------------------

_driver: Optional[AsyncDriver] = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            max_connection_lifetime=1800,
            connection_acquisition_timeout=30,
            keep_alive=True,
            liveness_check_timeout=10,
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


# ---------------------------------------------------------------------------
# Index bootstrap
# ---------------------------------------------------------------------------

async def ensure_indexes(driver: AsyncDriver) -> None:
    async with driver.session(database=settings.neo4j_database) as session:
        for stmt in (
            _IDX_CHUNK, _IDX_DOCUMENT, _IDX_SERVICE,
            _IDX_LIBRARY, _IDX_INCIDENT, _IDX_TEAM,
        ):
            await session.run(stmt)


# ---------------------------------------------------------------------------
# Entity helpers
# ---------------------------------------------------------------------------

async def _merge_entity(session, label: str, name: str, team_id: str, version: Optional[str]) -> None:
    if label == "Service":
        await session.run(_MERGE_SERVICE, name=name, team_id=team_id)
    elif label == "Library":
        await session.run(_MERGE_LIBRARY, name=name, version=version)
    elif label == "Incident":
        await session.run(_MERGE_INCIDENT, name=name, team_id=team_id)
    elif label == "Team":
        await session.run(_MERGE_TEAM, name=name)


def _build_rel_merge(from_label: str, rel_type: str, to_label: str) -> str:
    from_key = _LABEL_ID_PROP[from_label]
    to_key = _LABEL_ID_PROP[to_label]
    return (
        f"MERGE (a:{from_label} {{{from_key}: $from_name}})\n"
        f"MERGE (b:{to_label}   {{{to_key}: $to_name}})\n"
        f"MERGE (a)-[:{rel_type}]->(b)"
    )


async def _merge_relationship(
    session,
    from_label: str,
    from_name: str,
    rel_type: str,
    to_label: str,
    to_name: str,
) -> None:
    if (
        from_label not in _VALID_LABELS
        or to_label not in _VALID_LABELS
        or rel_type not in _VALID_REL_TYPES
    ):
        logger.warning(
            "writer: skipping relationship with invalid labels/rel_type: %s -[%s]-> %s",
            from_label, rel_type, to_label,
        )
        return
    cypher = _build_rel_merge(from_label, rel_type, to_label)
    await session.run(cypher, from_name=from_name, to_name=to_name)


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------

async def upsert_document(doc, driver: AsyncDriver) -> None:
    async with driver.session(database=settings.neo4j_database) as session:
        await session.run(
            _MERGE_DOCUMENT,
            doc_id=doc.doc_id,
            title=doc.title,
            source=doc.source_url,
            source_type=doc.source_type,
            team_id=doc.team_id,
        )


async def upsert_chunk(chunk, extraction: ExtractionResult, driver: AsyncDriver) -> None:
    async with driver.session(database=settings.neo4j_database) as session:
        await session.run(
            _MERGE_CHUNK,
            chunk_id=chunk.chunk_id,
            qdrant_id=chunk.chunk_id,
            text=chunk.text,
            source=chunk.source,
            source_type=chunk.source_type,
            team_id=chunk.team_id,
            chunk_index=chunk.chunk_index,
            channel_id=getattr(chunk, "channel_id", None),
        )
        await session.run(
            _MERGE_HAS_CHUNK,
            doc_id=chunk.doc_id,
            chunk_id=chunk.chunk_id,
        )

        for entity in extraction.entities:
            await _merge_entity(
                session,
                label=entity.label,
                name=entity.name,
                team_id=chunk.team_id,
                version=entity.version,
            )

        for rel in extraction.relationships:
            from_name = chunk.chunk_id if rel.from_label == "Chunk" else rel.from_name
            await _merge_relationship(
                session,
                from_label=rel.from_label,
                from_name=from_name,
                rel_type=rel.rel_type,
                to_label=rel.to_label,
                to_name=rel.to_name,
            )
