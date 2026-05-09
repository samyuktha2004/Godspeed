from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ingestion.models import DocumentChunk
from src.file_agent.config import file_config

logger = logging.getLogger(__name__)


def _word_windows(text: str, max_words: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    parts = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words])
        if chunk.strip():
            parts.append(chunk)
    return parts


def _format_table_rows(rows: list[list[str]]) -> str:
    return "\n".join(" | ".join(str(c) for c in row) for row in rows)


def chunk_file_content(
    blocks: list[dict[str, Any]],
    file_path: str,
    team_id: str,
    max_words: int = 0,
) -> list[DocumentChunk]:
    max_words = max_words or file_config.max_words_per_chunk
    file_name = Path(file_path).name
    file_url = f"file://{Path(file_path).resolve().as_posix()}"
    doc_id = hashlib.sha256(f"file:{file_name}".encode()).hexdigest()
    chunks: list[DocumentChunk] = []

    for block_idx, block in enumerate(blocks):
        btype = block.get("type", "text")
        content = block.get("content", "")
        heading = block.get("heading", block.get("tag_path", ""))
        page = block.get("page", "")
        sheet = block.get("sheet", "")

        base_meta = {
            "file_name": file_name,
            "block_index": block_idx,
            "block_type": btype,
        }
        if page:
            base_meta["page"] = page
        if sheet:
            base_meta["sheet"] = sheet

        if btype in ("table",):
            if isinstance(content, list):
                text = _format_table_rows(content)
            else:
                text = str(content)
            prefix = f"File: {file_name}\nTable:\n"
            chunk_id = hashlib.sha256(f"file:{file_name}:block_{block_idx}_part_0".encode()).hexdigest()
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=(prefix + text).strip(),
                    source=file_url,
                    source_type="file",
                    team_id=team_id,
                    chunk_index=len(chunks),
                    metadata={**base_meta, "title": file_name},
                )
            )

        elif btype == "row":
            text = str(content)
            prefix = f"File: {file_name}\nRow: "
            chunk_id = hashlib.sha256(f"file:{file_name}:block_{block_idx}_part_0".encode()).hexdigest()
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=(prefix + text).strip(),
                    source=file_url,
                    source_type="file",
                    team_id=team_id,
                    chunk_index=len(chunks),
                    metadata={**base_meta, "title": file_name},
                )
            )

        else:
            # text / section / xml_node — word-window split
            text = str(content).strip()
            if not text:
                continue
            heading_line = f"Section: {heading}\n\n" if heading else ""
            prefix = f"File: {file_name}\n{heading_line}"
            parts = _word_windows(text, max_words)
            for part_idx, part in enumerate(parts):
                chunk_id = hashlib.sha256(
                    f"file:{file_name}:block_{block_idx}_part_{part_idx}".encode()
                ).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        text=(prefix + part).strip(),
                        source=file_url,
                        source_type="file",
                        team_id=team_id,
                        chunk_index=len(chunks),
                        metadata={**base_meta, "title": file_name, "section_heading": heading},
                    )
                )

    logger.debug("file_chunker: %s -> %d chunks from %d blocks", file_name, len(chunks), len(blocks))
    return chunks
