from __future__ import annotations

import hashlib
import logging
from typing import Optional

import spacy

from ingestion.config import settings
from ingestion.models import DocumentChunk, RawDocument

logger = logging.getLogger(__name__)

_nlp: Optional[spacy.language.Language] = None


def _get_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        logger.info("chunker: loading spacy model %s", settings.spacy_model)
        _nlp = spacy.load(settings.spacy_model, disable=["ner", "parser"])
        _nlp.enable_pipe("senter")
    return _nlp


def _token_count(nlp: spacy.language.Language, text: str) -> int:
    return len(nlp.tokenizer(text))


def chunk_document(doc: RawDocument) -> list[DocumentChunk]:
    nlp = _get_nlp()
    spacy_doc = nlp(doc.content)
    sentences = [s.text.strip() for s in spacy_doc.sents if s.text.strip()]

    if not sentences:
        return []

    token_counts = [_token_count(nlp, s) for s in sentences]
    target = settings.chunk_target_tokens
    hard_max = settings.chunk_max_tokens
    overlap_budget = int(target * settings.chunk_overlap_ratio)

    chunks: list[DocumentChunk] = []
    chunk_start = 0

    while chunk_start < len(sentences):
        accumulated = 0
        chunk_end = chunk_start

        while chunk_end < len(sentences):
            next_count = token_counts[chunk_end]
            # Force-include at least one sentence even if it exceeds hard_max
            if accumulated + next_count > hard_max and accumulated > 0:
                break
            accumulated += next_count
            chunk_end += 1
            if accumulated >= target:
                break

        text = " ".join(sentences[chunk_start:chunk_end])
        chunk_id = hashlib.sha256(
            f"{doc.doc_id}:{chunk_start}:{chunk_end}".encode()
        ).hexdigest()
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc.doc_id,
                text=text,
                source=doc.source_url,
                source_type=doc.source_type,
                team_id=doc.team_id,
                chunk_index=len(chunks),
                metadata={**doc.metadata, "title": doc.title},
            )
        )

        # Walk back from chunk_end to find the overlap window for the next chunk
        overlap_tokens = 0
        overlap_start = chunk_end
        while overlap_start > chunk_start + 1:
            candidate = overlap_start - 1
            if overlap_tokens + token_counts[candidate] <= overlap_budget:
                overlap_tokens += token_counts[candidate]
                overlap_start = candidate
            else:
                break

        # Guard: if overlap would not advance the cursor, step forward unconditionally
        next_start = overlap_start if overlap_start > chunk_start else chunk_end
        if next_start <= chunk_start:
            next_start = chunk_end

        chunk_start = next_start

    logger.debug("chunker: %s -> %d chunks", doc.doc_id, len(chunks))
    return chunks
