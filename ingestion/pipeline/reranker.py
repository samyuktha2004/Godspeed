from __future__ import annotations

import logging
from typing import Optional

from FlagEmbedding import FlagReranker

from ingestion.config import settings

logger = logging.getLogger(__name__)

_reranker: Optional[FlagReranker] = None


def _get_reranker() -> FlagReranker:
    global _reranker
    if _reranker is None:
        logger.info("reranker: loading model %s", settings.bge_reranker_model)
        _reranker = FlagReranker(settings.bge_reranker_model, use_fp16=True)
    return _reranker


def rerank(query: str, texts: list[str], normalize: bool = True) -> list[float]:
    if not texts:
        return []
    reranker = _get_reranker()
    pairs = [(query, t) for t in texts]
    try:
        return reranker.compute_score(pairs, normalize=normalize)
    except Exception:
        logger.exception("reranker: compute_score failed")
        return [0.0] * len(texts)
