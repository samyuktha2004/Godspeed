from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ingestion.config import settings
from ingestion.models import EmbeddedChunk

logger = logging.getLogger(__name__)


def _chunk_uuid(chunk_id: str) -> str:
    # stable UUID derived from chunk_id so re-ingestion overwrites the same point
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


# Fields the query path filters on (RBAC + Phase-1 routing scope + delete-by-doc).
# Keyword payload indexes keep these filters fast as the collection grows.
_PAYLOAD_INDEX_FIELDS = ("team_id", "channel_id", "source_type", "space_key", "repo", "doc_id")
_indexes_ensured = False


def ensure_payload_indexes() -> None:
    """Idempotently create keyword payload indexes on the fields we filter by.

    Runs once per process. Safe on an existing, populated collection — Qdrant
    builds each index over current points. Each call is best-effort: an
    already-existing index simply no-ops.
    """
    global _indexes_ensured
    if _indexes_ensured:
        return
    client = _get_client()
    for field in _PAYLOAD_INDEX_FIELDS:
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # Index already exists (or collection not ready) — idempotent, ignore.
            logger.debug("qdrant_store: payload index for %r skipped/exists", field, exc_info=True)
    _indexes_ensured = True
    logger.info("qdrant_store: ensured payload indexes on %s", ", ".join(_PAYLOAD_INDEX_FIELDS))


def _get_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection_exists() -> None:
    client = _get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection in existing:
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            settings.qdrant_dense_vector_name: qmodels.VectorParams(
                size=settings.qdrant_dense_size,
                distance=qmodels.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            settings.qdrant_sparse_vector_name: qmodels.SparseVectorParams(
                index=qmodels.SparseIndexParams(on_disk=settings.qdrant_sparse_on_disk)
            )
        },
    )
    logger.info("qdrant_store: created collection %s", settings.qdrant_collection)


def upsert_chunks(chunks: list[EmbeddedChunk]) -> None:
    if not chunks:
        return

    try:
        ensure_collection_exists()
        ensure_payload_indexes()
        client = _get_client()

        points = [
            qmodels.PointStruct(
                id=_chunk_uuid(chunk.chunk_id),
                vector={
                    settings.qdrant_dense_vector_name: chunk.dense_vector,
                    settings.qdrant_sparse_vector_name: qmodels.SparseVector(
                        indices=chunk.sparse_indices,
                        values=chunk.sparse_values,
                    ),
                },
                payload={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "source": chunk.source,
                    "source_type": chunk.source_type,
                    "team_id": chunk.team_id,
                    # RBAC channel key — the query-time filter matches on this.
                    # May be None for workspace-wide/legacy content (handled by
                    # the team_id-plus-null fallback branch in doc_search).
                    "channel_id": chunk.channel_id,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
        ]

        client.upsert(collection_name=settings.qdrant_collection, points=points)
        logger.info("qdrant_store: upserted %d points", len(points))

    except Exception:
        logger.exception("qdrant_store: upsert failed")
        raise


def delete_chunks_for_doc(doc_id: str) -> None:
    from qdrant_client.http.exceptions import UnexpectedResponse

    try:
        client = _get_client()
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))]
                )
            ),
        )
        logger.info("qdrant_store: deleted points for doc_id=%s", doc_id)
    except UnexpectedResponse as exc:
        # First ingest into a fresh Qdrant: collection doesn't exist yet, so there's
        # nothing to delete. upsert_chunks will create the collection on first write.
        if exc.status_code == 404:
            logger.info(
                "qdrant_store: collection %s does not exist yet — skipping delete for doc_id=%s",
                settings.qdrant_collection, doc_id,
            )
            return
        logger.exception("qdrant_store: delete failed for doc_id=%s", doc_id)
        raise
    except Exception:
        logger.exception("qdrant_store: delete failed for doc_id=%s", doc_id)
        raise
