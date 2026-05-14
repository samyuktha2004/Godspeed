from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import List

from rank_bm25 import BM25Okapi

from ingestion.config import settings

logger = logging.getLogger(__name__)


class BM25Store:
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def tokenize(text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"\b\w+\b", text.lower())

    def rebuild_index(self, chunk_ids: List[str], texts: List[str]) -> None:
        if not chunk_ids or not texts:
            logger.warning("BM25: empty corpus provided")
            return
        if len(chunk_ids) != len(texts):
            raise ValueError(f"chunk_ids ({len(chunk_ids)}) != texts ({len(texts)})")

        cleaned_ids, cleaned_texts, tokenized_corpus = [], [], []
        for chunk_id, text in zip(chunk_ids, texts):
            if not chunk_id or not text or not text.strip():
                continue
            tokens = self.tokenize(text)
            if not tokens:
                continue
            cleaned_ids.append(chunk_id)
            cleaned_texts.append(text)
            tokenized_corpus.append(tokens)

        if not tokenized_corpus:
            raise ValueError("No valid documents to index")

        with self.index_path.open("wb") as f:
            pickle.dump({"index": BM25Okapi(tokenized_corpus), "doc_ids": cleaned_ids, "corpus": cleaned_texts}, f)

        logger.info("BM25 rebuilt with %d documents -> %s", len(cleaned_ids), self.index_path)

    def load_index(self) -> dict:
        if not self.index_path.exists():
            raise FileNotFoundError(f"BM25 index not found: {self.index_path}")
        with self.index_path.open("rb") as f:
            return pickle.load(f)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        data = self.load_index()
        tokens = self.tokenize(query)
        if not tokens:
            return []
        scores = data["index"].get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"chunk_id": data["doc_ids"][i], "text": data["corpus"][i], "score": float(s)} for i, s in ranked]


# ── Module-level helpers (used by ingest_job.py) ─────────────────────────────

def rebuild_from_supabase() -> None:
    from ingestion.storage.supabase_store import get_all_chunks
    rows = get_all_chunks()
    if not rows:
        logger.warning("bm25_store: no chunks in Supabase, skipping rebuild")
        return
    store = BM25Store(settings.bm25_index_path)
    store.rebuild_index(
        chunk_ids=[r["chunk_id"] for r in rows],
        texts=[r["text"] for r in rows],
    )
