from __future__ import annotations

import logging
from typing import Optional

from FlagEmbedding import BGEM3FlagModel

from ingestion.config import settings
from ingestion.models import DocumentChunk, EmbeddedChunk

logger = logging.getLogger(__name__)

# loaded once at module level — BGE-M3 is large; per-request init is unacceptable latency
_model: Optional[BGEM3FlagModel] = None


def _get_model() -> BGEM3FlagModel:
    global _model
    if _model is None:
        logger.info("embedder: loading BGE-M3 model %s", settings.bge_embedding_model)
        _model = BGEM3FlagModel(settings.bge_embedding_model, use_fp16=True)
    return _model


def embed_chunks(chunks: list[DocumentChunk]) -> list[EmbeddedChunk]:
    if not chunks:
        return []

    model = _get_model()
    batch_size = settings.embed_batch_size
    embedded: list[EmbeddedChunk] = []

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [c.text for c in batch]

        output = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=batch_size,
        )

        for i, chunk in enumerate(batch):
            dense_vector: list[float] = output["dense_vecs"][i].tolist()
            # lexical_weights keys are token ids (int); values are float weights
            sparse_weights: dict[int, float] = output["lexical_weights"][i]
            sparse_indices = list(sparse_weights.keys())
            sparse_values = [sparse_weights[k] for k in sparse_indices]

            embedded.append(
                EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    source=chunk.source,
                    source_type=chunk.source_type,
                    team_id=chunk.team_id,
                    chunk_index=chunk.chunk_index,
                    dense_vector=dense_vector,
                    sparse_indices=sparse_indices,
                    sparse_values=sparse_values,
                    metadata=chunk.metadata,
                )
            )

        logger.debug(
            "embedder: embedded batch %d-%d of %d",
            batch_start,
            batch_start + len(batch),
            len(chunks),
        )

    return embedded
