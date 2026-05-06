from __future__ import annotations

import logging
from pathlib import Path

from ingestion.pipeline.embedder import embed_chunks
from ingestion.pipeline.pii_masker import mask_chunks
from ingestion.storage.qdrant_store import delete_chunks_for_doc, upsert_chunks
from src.file_agent.chunker import chunk_file_content
from src.file_agent.config import file_config
from src.file_agent.detector import detect_format
from src.file_agent.parsers import dispatch

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {"pdf", "docx", "xml", "text", "csv", "xlsx", "html"}


def process_file(file_path: str, team_id: str = "") -> int:
    """
    Full pipeline: detect → parse → chunk → PII mask → embed → upsert Qdrant.
    Returns the number of chunks stored. Raises on fatal errors.
    """
    team_id = team_id or file_config.team_id
    fmt = detect_format(file_path)

    if fmt not in _SUPPORTED_FORMATS:
        logger.warning("file_pipeline: unsupported format %r for %s", fmt, file_path)
        return 0

    blocks = dispatch(file_path, fmt)
    if not blocks:
        logger.warning("file_pipeline: no blocks extracted from %s", file_path)
        return 0

    chunks = chunk_file_content(blocks, file_path, team_id)
    if not chunks:
        logger.warning("file_pipeline: no chunks produced for %s", file_path)
        return 0

    texts = [c.text for c in chunks]
    masked = mask_chunks(texts)
    for chunk, m in zip(chunks, masked):
        chunk.text = m

    embedded = embed_chunks(chunks)

    # Idempotent: all chunks share the same doc_id derived from file name
    doc_id = embedded[0].doc_id
    delete_chunks_for_doc(doc_id)
    upsert_chunks(embedded)

    logger.info("file_pipeline: stored %d chunks for %s (format=%s)", len(embedded), Path(file_path).name, fmt)
    return len(embedded)
