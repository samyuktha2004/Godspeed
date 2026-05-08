from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ingestion.models import RawDocument
from ingestion.pipeline.embedder import embed_chunks
from ingestion.pipeline.pii_masker import mask_chunks
from ingestion.storage import supabase_store
from ingestion.storage.qdrant_store import delete_chunks_for_doc, upsert_chunks
from src.file_agent.chunker import chunk_file_content
from src.file_agent.config import file_config
from src.file_agent.detector import detect_format
from src.file_agent.parsers import dispatch

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {"pdf", "docx", "xml", "text", "csv", "xlsx", "html"}


def _store(raw_doc, embedded):
    supabase_store.upsert_document(raw_doc)
    supabase_store.delete_chunks_for_doc(raw_doc.doc_id)
    supabase_store.upsert_chunks(embedded)
    delete_chunks_for_doc(raw_doc.doc_id)
    upsert_chunks(embedded)


def process_file(file_path: str, team_id: str = "") -> int:
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
    file_name = Path(file_path).name
    doc_id = hashlib.sha256(f"file:{file_name}".encode()).hexdigest()
    raw_doc = RawDocument(
        doc_id=doc_id,
        title=file_name,
        content="",
        source_url=f"file://{Path(file_path).resolve().as_posix()}",
        source_type="file",
        team_id=team_id,
        metadata={"file_name": file_name, "format": fmt},
    )
    _store(raw_doc, embedded)

    logger.info("file_pipeline: stored %d chunks for %s (format=%s)", len(embedded), file_name, fmt)
    return len(embedded)
