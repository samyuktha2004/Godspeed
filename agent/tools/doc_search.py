"""Qdrant hybrid retrieval with BGE-M3 embeddings, BM25, RRF fusion, and reranking."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from rank_bm25 import BM25Okapi

from agent.config import settings
from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)


def _get_qdrant_client() -> AsyncQdrantClient:
    """Return Qdrant client — cloud if QDRANT_URL is set, otherwise local."""
    if settings.qdrant_url:
        return AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

_PII_ENTITY_TYPES = [
    "person",
    "email",
    "phone",
    "ssn",
    "credit_card",
    "address",
    "date_of_birth",
]

# singletons — loaded once on first call, models are expensive to initialise
_embedding_model = None
_reranker = None
_gliner = None
_bm25_index: Optional[BM25Okapi] = None
_bm25_corpus: Optional[list[str]] = None
_bm25_doc_ids: Optional[list[str]] = None
_bm25_metadata: Optional[list[dict]] = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from FlagEmbedding import BGEM3FlagModel
        logger.info("Loading BGE-M3 embedding model: %s", settings.bge_embedding_model)
        _embedding_model = BGEM3FlagModel(settings.bge_embedding_model, use_fp16=True)
    return _embedding_model


def _get_reranker():
    global _reranker
    if _reranker is None:
        import numpy as np
        from sentence_transformers import CrossEncoder
        logger.info("Loading CrossEncoder reranker (ms-marco-MiniLM-L-6-v2)")
        _model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        class _Reranker:
            def compute_score(self, pairs, normalize=True):
                raw = _model.predict(pairs)
                if normalize:
                    return list(1 / (1 + np.exp(-raw)))
                return list(raw.tolist())
        _reranker = _Reranker()
    return _reranker


def _get_gliner():
    global _gliner
    if _gliner is None:
        from gliner import GLiNER
        logger.info("Loading GLiNER model: %s", settings.gliner_model)
        _gliner = GLiNER.from_pretrained(settings.gliner_model)
    return _gliner


def _load_bm25() -> tuple[Optional[BM25Okapi], Optional[list[str]], Optional[list[str]], Optional[list[dict]]]:
    global _bm25_index, _bm25_corpus, _bm25_doc_ids, _bm25_metadata
    if _bm25_index is not None:
        return _bm25_index, _bm25_corpus, _bm25_doc_ids, _bm25_metadata

    index_path = Path(settings.bm25_index_path)
    if not index_path.exists():
        logger.warning("BM25 index not found at %s — skipping BM25 retrieval", index_path)
        return None, None, None, None

    try:
        with index_path.open("rb") as f:
            data = pickle.load(f)
        _bm25_index = data["index"]
        _bm25_corpus = data["corpus"]
        _bm25_doc_ids = data["doc_ids"]
        _bm25_metadata = data.get("metadata")
        logger.info("Loaded BM25 index with %d documents", len(_bm25_doc_ids))
    except Exception:
        logger.exception("Failed to load BM25 index from %s", index_path)
        return None, None, None, None

    return _bm25_index, _bm25_corpus, _bm25_doc_ids, _bm25_metadata


def _mask_pii(text: str) -> str:
    try:
        gliner = _get_gliner()
        entities = gliner.predict_entities(text, _PII_ENTITY_TYPES, threshold=0.5)
        # iterate reverse so substring replacements don't shift later indices
        entities_sorted = sorted(entities, key=lambda e: e["start"], reverse=True)
        masked = text
        for ent in entities_sorted:
            masked = masked[: ent["start"]] + "[REDACTED]" + masked[ent["end"] :]
        return masked
    except Exception:
        logger.exception("GLiNER PII masking failed; using raw query")
        return text


def _reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = 60
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


async def run_doc_search(
    query: str,
    team_id: str,
    allowed_channel_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    masked_query = _mask_pii(query)
    logger.info("doc_search: masked query = %r", masked_query)

    embed_model = _get_embedding_model()
    output = embed_model.encode(
        [masked_query],
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense_vector: list[float] = output["dense_vecs"][0].tolist()
    sparse_weights: dict[int, float] = output["lexical_weights"][0]

    sparse_indices = list(sparse_weights.keys())
    sparse_values = [sparse_weights[i] for i in sparse_indices]

    bm25_ranked_ids: list[str] = []
    bm25, corpus, doc_ids, bm25_metadata = _load_bm25()
    if bm25 is not None and doc_ids:
        tokenized = masked_query.lower().split()
        bm25_scores = bm25.get_scores(tokenized)
        top_bm25_idx = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )[: settings.rrf_top_k]
        bm25_ranked_ids = [doc_ids[i] for i in top_bm25_idx]

    qdrant_ranked_ids: list[str] = []
    qdrant_payload_map: dict[str, dict] = {}
    qdrant_score_map: dict[str, float] = {}

    try:
        client = _get_qdrant_client()

        # Channel-based filter (RBAC): use allowed_channel_ids when set.
        # Falls back to team_id for legacy points that pre-date channel tagging.
        if allowed_channel_ids:
            qdrant_filter = qmodels.Filter(
                should=[
                    # New RBAC path: chunk tagged with an allowed channel
                    qmodels.FieldCondition(
                        key="channel_id",
                        match=qmodels.MatchAny(any=allowed_channel_ids),
                    ),
                    # Legacy path: chunk has no channel_id but matches team_id
                    qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(key="team_id", match=qmodels.MatchValue(value=team_id)),
                            qmodels.IsNullCondition(is_null=qmodels.PayloadField(key="channel_id")),
                        ]
                    ),
                ]
            )
        else:
            qdrant_filter = qmodels.Filter(
                must=[qmodels.FieldCondition(key="team_id", match=qmodels.MatchValue(value=team_id))]
            )

        dense_response = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=dense_vector,
            using=settings.qdrant_dense_vector_name,
            query_filter=qdrant_filter,
            limit=settings.rrf_top_k,
            with_payload=True,
        )
        for hit in dense_response.points:
            doc_id = hit.payload.get("chunk_id", str(hit.id))
            qdrant_ranked_ids.append(doc_id)
            qdrant_payload_map[doc_id] = hit.payload
            qdrant_score_map[doc_id] = hit.score

        sparse_response = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=qmodels.SparseVector(indices=sparse_indices, values=sparse_values),
            using=settings.qdrant_sparse_vector_name,
            query_filter=qdrant_filter,
            limit=settings.rrf_top_k,
            with_payload=True,
        )
        sparse_ranked_ids: list[str] = []
        for hit in sparse_response.points:
            doc_id = hit.payload.get("chunk_id", str(hit.id))
            sparse_ranked_ids.append(doc_id)
            qdrant_payload_map.setdefault(doc_id, hit.payload)
            qdrant_score_map.setdefault(doc_id, hit.score)

        await client.close()

    except Exception:
        logger.exception("Qdrant search failed — returning empty results")
        sparse_ranked_ids = []

    ranked_lists = [lst for lst in [qdrant_ranked_ids, sparse_ranked_ids, bm25_ranked_ids] if lst]
    if not ranked_lists:
        logger.warning("All retrieval sources returned empty — no results")
        return []

    rrf_scores = _reciprocal_rank_fusion(ranked_lists)
    top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[: settings.rrf_top_k]

    candidates: list[dict] = []
    for doc_id in top_ids:
        payload = qdrant_payload_map.get(doc_id)
        if payload is None:
            # BM25-only hit has no Qdrant payload — reconstruct from corpus
            if doc_ids and doc_id in doc_ids:
                idx = doc_ids.index(doc_id)
                text = corpus[idx] if corpus else ""
                meta = bm25_metadata[idx] if bm25_metadata else {}
                payload = {
                    "chunk_id": doc_id,
                    "text": text,
                    "source": meta.get("source") or meta.get("source_url") or "bm25",
                    "source_type": meta.get("source_type", "internal"),
                }
            else:
                continue
        candidates.append({"id": doc_id, "payload": payload, "rrf_score": rrf_scores[doc_id]})

    if not candidates:
        return []

    reranker = _get_reranker()
    pairs = [(masked_query, c["payload"].get("text", "")) for c in candidates]
    try:
        rerank_scores: list[float] = reranker.compute_score(pairs, normalize=True)
    except Exception:
        logger.exception("Reranker failed — falling back to RRF scores")
        rerank_scores = [c["rrf_score"] for c in candidates]

    for i, cand in enumerate(candidates):
        cand["reranker_score"] = rerank_scores[i]

    candidates.sort(key=lambda c: c["reranker_score"], reverse=True)
    top_candidates = candidates[: settings.final_top_k]

    chunks: list[RetrievedChunk] = []
    for cand in top_candidates:
        p = cand["payload"]
        chunks.append(
            RetrievedChunk(
                chunk_id=p.get("chunk_id", cand["id"]),
                text=p.get("text", ""),
                source=p.get("source", "unknown"),
                source_type=p.get("source_type", "internal"),
                score=cand["rrf_score"],
                reranker_score=cand["reranker_score"],
                title=p.get("title"),
            )
        )

    logger.info(
        "doc_search: returning %d chunks, top reranker score=%.3f",
        len(chunks),
        chunks[0].reranker_score if chunks else 0.0,
    )
    return chunks


def compute_retrieval_confidence(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "low"
    top_score = chunks[0].reranker_score or 0.0
    if top_score >= settings.reranker_high_threshold:
        return "high"
    if top_score >= settings.reranker_medium_threshold:
        return "medium"
    return "low"
