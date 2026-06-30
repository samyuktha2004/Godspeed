from __future__ import annotations

import hashlib

from ingestion.models import DocumentChunk, RawDocument
from src.utils.logger import get_logger

logger = get_logger(__name__)


def chunk_jira_issue(raw_doc: RawDocument) -> list[DocumentChunk]:
    """
    Issue body → chunk 0.
    Each comment → one chunk per comment.
    Stable chunk_ids so re-ingestion overwrites existing vectors.
    """
    key = raw_doc.metadata.get("issue_key", raw_doc.doc_id)
    chunks: list[DocumentChunk] = []

    # Chunk 0: issue body
    body_text = raw_doc.content
    if body_text.strip():
        chunk_id = hashlib.sha256(f"jira:{key}:0".encode()).hexdigest()
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=raw_doc.doc_id,
                text=body_text,
                source=raw_doc.source_url,
                source_type="jira",
                team_id=raw_doc.team_id,
                chunk_index=0,
                metadata={
                    **{k: v for k, v in raw_doc.metadata.items() if k != "comments"},
                    "title": raw_doc.title,
                    "type": "issue_body",
                },
            )
        )

    # Chunks 1..N: comments
    comments = raw_doc.metadata.get("comments", [])
    skipped_comments = 0
    for idx, comment in enumerate(comments, start=1):
        author = comment.get("author", "Unknown")
        body = comment.get("body", "").strip()
        if not body:
            skipped_comments += 1
            continue
        text = f"Comment on {key} by {author}:\n{body}"
        chunk_id = hashlib.sha256(f"jira:{key}:{idx}".encode()).hexdigest()
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=raw_doc.doc_id,
                text=text,
                source=raw_doc.source_url,
                source_type="jira",
                team_id=raw_doc.team_id,
                chunk_index=idx,
                metadata={
                    **{k: v for k, v in raw_doc.metadata.items() if k != "comments"},
                    "title": raw_doc.title,
                    "type": "comment",
                    "comment_index": idx - 1,
                    "comment_author": author,
                },
            )
        )

    logger.info(
        "jira_issue_chunked",
        extra={
            "doc_id": raw_doc.doc_id,
            "team_id": raw_doc.team_id,
            "comment_count": len(comments),
            "skipped_comments": skipped_comments,
            "chunk_count": len(chunks),
        },
    )

    return chunks
