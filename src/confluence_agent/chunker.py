from __future__ import annotations

import hashlib
import logging
from typing import Optional

from ingestion.models import DocumentChunk, RawDocument

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup, Tag

    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False
    logger.warning("confluence_chunker: beautifulsoup4 not installed; falling back to plain strip")

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_MAX_CHUNK_CHARS = 4000


def _build_breadcrumb(raw_doc: RawDocument) -> str:
    parts: list[str] = []
    space_key = raw_doc.metadata.get("space_key", "")
    if space_key:
        parts.append(space_key)
    for anc in raw_doc.metadata.get("ancestors", []):
        if anc:
            parts.append(anc)
    parts.append(raw_doc.title)
    return " > ".join(parts)


def _format_table(table_tag) -> str:
    rows = []
    for tr in table_tag.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def _make_chunk(
    raw_doc: RawDocument,
    text: str,
    heading: str,
    breadcrumb: str,
    chunk_index: int,
    section_idx: int,
    part_idx: int,
    extra_meta: Optional[dict] = None,
) -> DocumentChunk:
    prefix = f"[{breadcrumb}]\nSection: {heading}\n\n" if heading else f"[{breadcrumb}]\n\n"
    full_text = prefix + text.strip()
    chunk_id = hashlib.sha256(
        f"confluence:{raw_doc.metadata['page_id']}:section_{section_idx}_part_{part_idx}".encode()
    ).hexdigest()
    meta = {
        "page_id": raw_doc.metadata.get("page_id"),
        "space_key": raw_doc.metadata.get("space_key"),
        "title": raw_doc.title,
        "section_heading": heading,
        "breadcrumb": breadcrumb,
    }
    if extra_meta:
        meta.update(extra_meta)
    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id=raw_doc.doc_id,
        text=full_text,
        source=raw_doc.source_url,
        source_type="confluence",
        team_id=raw_doc.team_id,
        chunk_index=chunk_index,
        metadata=meta,
    )


def _split_long_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text into parts of at most max_chars, breaking on word boundaries."""
    if len(text) <= max_chars:
        return [text]
    parts = []
    while len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars)
        if cut == -1:
            cut = max_chars
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


def chunk_confluence_page(raw_doc: RawDocument) -> list[DocumentChunk]:
    """
    Parse Confluence Storage Format HTML using BeautifulSoup.
    Produces heading-split section chunks + one chunk per table.
    Falls back to single-chunk plain strip if BS4 is unavailable.
    """
    if not _BS4_AVAILABLE:
        return _fallback_single_chunk(raw_doc)

    html = raw_doc.content
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    breadcrumb = _build_breadcrumb(raw_doc)
    chunks: list[DocumentChunk] = []
    chunk_index = 0
    section_idx = 0

    # Extract tables first and remove from DOM so they don't bleed into text chunks
    tables = soup.find_all("table")
    table_chunks = []
    for t_idx, table in enumerate(tables):
        table_text = _format_table(table)
        table.decompose()
        if table_text.strip():
            tbl_chunk = _make_chunk(
                raw_doc, table_text, "Table", breadcrumb, chunk_index, section_idx, 0,
                extra_meta={"type": "table", "table_index": t_idx},
            )
            table_chunks.append(tbl_chunk)
            chunk_index += 1
            section_idx += 1

    # Walk top-level elements, break on heading tags
    current_heading = ""
    current_text_parts: list[str] = []

    def _flush(heading: str, parts: list[str], s_idx: int) -> int:
        nonlocal chunk_index
        text = " ".join(parts).strip()
        if not text:
            return s_idx
        for p_idx, segment in enumerate(_split_long_text(text)):
            c = _make_chunk(raw_doc, segment, heading, breadcrumb, chunk_index, s_idx, p_idx)
            chunks.append(c)
            chunk_index += 1
        return s_idx + 1

    for element in soup.body.children if soup.body else soup.children:
        if not hasattr(element, "name") or element.name is None:
            # NavigableString
            t = str(element).strip()
            if t:
                current_text_parts.append(t)
            continue
        if element.name in _HEADING_TAGS:
            section_idx = _flush(current_heading, current_text_parts, section_idx)
            current_heading = element.get_text(" ", strip=True)
            current_text_parts = []
        else:
            t = element.get_text(" ", strip=True)
            if t:
                current_text_parts.append(t)

    section_idx = _flush(current_heading, current_text_parts, section_idx)

    # Append table chunks after text chunks
    chunks.extend(table_chunks)

    logger.debug("confluence_chunker: %s -> %d chunks", raw_doc.doc_id, len(chunks))
    return chunks


def _fallback_single_chunk(raw_doc: RawDocument) -> list[DocumentChunk]:
    import re
    text = re.sub(r"<[^>]+>", " ", raw_doc.content)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if not text:
        return []
    breadcrumb = _build_breadcrumb(raw_doc)
    chunk_id = hashlib.sha256(
        f"confluence:{raw_doc.metadata['page_id']}:section_0_part_0".encode()
    ).hexdigest()
    return [
        DocumentChunk(
            chunk_id=chunk_id,
            doc_id=raw_doc.doc_id,
            text=f"[{breadcrumb}]\n\n{text}",
            source=raw_doc.source_url,
            source_type="confluence",
            team_id=raw_doc.team_id,
            chunk_index=0,
            metadata={
                "page_id": raw_doc.metadata.get("page_id"),
                "space_key": raw_doc.metadata.get("space_key"),
                "title": raw_doc.title,
                "breadcrumb": breadcrumb,
            },
        )
    ]
