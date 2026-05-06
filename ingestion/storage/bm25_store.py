from __future__ import annotations

import logging
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

from ingestion.config import settings

logger = logging.getLogger(__name__)


def rebuild_bm25_index(chunk_ids: list[str], texts: list[str]) -> None:
    if not chunk_ids or not texts:
        logger.warning("bm25_store: no chunks provided, skipping rebuild")
        return

    if len(chunk_ids) != len(texts):
        raise ValueError("chunk_ids and texts must have equal length")

    tokenized_corpus = [t.lower().split() for t in texts]
    index = BM25Okapi(tokenized_corpus)

    index_path = Path(settings.bm25_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    with index_path.open("wb") as f:
        pickle.dump({"index": index, "corpus": texts, "doc_ids": chunk_ids}, f)

    logger.info("bm25_store: rebuilt index with %d documents -> %s", len(chunk_ids), index_path)


def rebuild_from_supabase() -> None:
    from ingestion.storage.supabase_store import get_all_chunks

    rows = get_all_chunks()
    if not rows:
        logger.warning("bm25_store: no chunks in Supabase, skipping rebuild")
        return

    chunk_ids = [r["chunk_id"] for r in rows]
    texts = [r["text"] for r in rows]
    rebuild_bm25_index(chunk_ids, texts)
