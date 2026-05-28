"""Confluence page search — retrieves ingested Confluence chunks from Qdrant."""

from __future__ import annotations

import logging

from agent.config import settings
from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)


async def run_confluence_search(query: str, team_id: str) -> list[RetrievedChunk]:
    """Search Qdrant for Confluence chunks matching the query."""
    from qdrant_client.http import models as qmodels
    from agent.tools.doc_search import _get_embedding_model, _get_qdrant_client

    client = None
    try:
        model = _get_embedding_model()
        output = model.encode(
            [query],
            batch_size=1,
            max_length=512,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vector = output["dense_vecs"][0].tolist()

        client = _get_qdrant_client()

        conf_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(key="source_type", match=qmodels.MatchValue(value="confluence")),
                qmodels.FieldCondition(key="team_id",     match=qmodels.MatchValue(value=team_id)),
            ]
        )

        response = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=dense_vector,
            using=settings.qdrant_dense_vector_name,
            query_filter=conf_filter,
            limit=10,
            with_payload=True,
        )

        chunks = []
        for hit in response.points:
            p = hit.payload or {}
            chunks.append(RetrievedChunk(
                chunk_id=p.get("chunk_id", str(hit.id)),
                text=p.get("text", ""),
                source=p.get("source", ""),
                source_type="confluence",
                score=hit.score,
                metadata=p.get("metadata", {}),
            ))

        logger.info("confluence_search: found %d chunks for query=%r team=%s", len(chunks), query, team_id)
        return chunks

    except Exception:
        logger.exception("confluence_search: search failed")
        return []
    # NOTE: do not close `client` — it is the shared singleton from
    # src.utils.clients; its lifetime is owned by the FastAPI lifespan hook.
