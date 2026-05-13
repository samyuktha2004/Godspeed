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


import logging
import pickle
import re
from pathlib import Path
from typing import List

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Store:
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """
        Better tokenizer than simple split().
        """
        if not text:
            return []

        text = text.lower()

        # keep words/numbers only
        tokens = re.findall(r"\b\w+\b", text)

        return tokens

    def rebuild_index(
        self,
        chunk_ids: List[str],
        texts: List[str],
    ) -> None:
        """
        Fully rebuild BM25 index.
        """

        if not chunk_ids or not texts:
            logger.warning("BM25: empty corpus provided")
            return

        if len(chunk_ids) != len(texts):
            raise ValueError(
                f"chunk_ids ({len(chunk_ids)}) "
                f"!= texts ({len(texts)})"
            )

        cleaned_ids = []
        cleaned_texts = []
        tokenized_corpus = []

        for chunk_id, text in zip(chunk_ids, texts):

            if not chunk_id:
                logger.warning("Skipping empty chunk_id")
                continue

            if not text or not text.strip():
                logger.warning(
                    "Skipping empty text for chunk_id=%s",
                    chunk_id,
                )
                continue

            tokens = self.tokenize(text)

            if not tokens:
                logger.warning(
                    "Skipping un-tokenizable text for chunk_id=%s",
                    chunk_id,
                )
                continue

            cleaned_ids.append(chunk_id)
            cleaned_texts.append(text)
            tokenized_corpus.append(tokens)

        if not tokenized_corpus:
            raise ValueError("No valid documents to index")

        bm25 = BM25Okapi(tokenized_corpus)

        payload = {
            "index": bm25,
            "doc_ids": cleaned_ids,
            "corpus": cleaned_texts,
        }

        with self.index_path.open("wb") as f:
            pickle.dump(payload, f)

        logger.info(
            "BM25 rebuilt successfully with %d documents",
            len(cleaned_ids),
        )

    def load_index(self):
        """
        Load BM25 index from disk.
        """

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"BM25 index not found: {self.index_path}"
            )

        with self.index_path.open("rb") as f:
            return pickle.load(f)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ):
        """
        Search BM25 index.
        """

        data = self.load_index()

        bm25: BM25Okapi = data["index"]
        doc_ids = data["doc_ids"]
        corpus = data["corpus"]

        tokenized_query = self.tokenize(query)

        if not tokenized_query:
            return []

        scores = bm25.get_scores(tokenized_query)

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        results = []

        for idx, score in ranked:
            results.append(
                {
                    "chunk_id": doc_ids[idx],
                    "text": corpus[idx],
                    "score": float(score),
                }
            )

        return results