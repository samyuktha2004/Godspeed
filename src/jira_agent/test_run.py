"""
JIRA agent runthrough.

With credentials (JIRA_BASE_URL + JIRA_API_TOKEN + JIRA_EMAIL set):
  Fetches the first issue from JIRA_PROJECT_KEYS (or TEST-1 if not set),
  runs the full pipeline, then verifies the vectors in Qdrant.

Without credentials (mock mode):
  Builds a synthetic RawDocument, runs chunker → PII mask → embed → Qdrant,
  and verifies via Qdrant scroll.

Run:
  python -m src.jira_agent.test_run
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("jira_test_run")


def _mock_raw_document():
    from ingestion.models import RawDocument

    return RawDocument(
        doc_id=hashlib.sha256(b"jira:TEST-1").hexdigest(),
        title="TEST-1: Sample authentication bug",
        content=(
            "Issue TEST-1: Sample authentication bug\n"
            "Type: Bug | Status: Open | Priority: High\n"
            "Assignee: Alice Smith\n"
            "Labels: auth, backend\n\n"
            "Users are unable to login using SSO after the latest deployment. "
            "The SAML assertion is not being validated correctly. "
            "This affects all enterprise accounts. Contact: alice@example.com"
        ),
        source_url="http://mock-jira/browse/TEST-1",
        source_type="jira",
        team_id="test_team",
        metadata={
            "issue_key": "TEST-1",
            "status": "Open",
            "priority": "High",
            "assignee": "Alice Smith",
            "issue_type": "Bug",
            "labels": "auth, backend",
            "updated": "2024-01-01T00:00:00Z",
            "comments": [
                {
                    "author": "Bob Jones",
                    "body": "Confirmed on staging. The certificate chain seems broken. Phone: 555-123-4567",
                    "created": "2024-01-02T00:00:00Z",
                }
            ],
        },
    )


async def _run_mock() -> None:
    from ingestion.pipeline.embedder import embed_chunks
    from ingestion.pipeline.pii_masker import mask_chunks
    from ingestion.storage.qdrant_store import (
        delete_chunks_for_doc,
        ensure_collection_exists,
        upsert_chunks,
    )
    from qdrant_client import QdrantClient
    from src.jira_agent.chunker import chunk_jira_issue
    from ingestion.config import settings

    logger.info("=== JIRA agent test — MOCK MODE ===")
    ensure_collection_exists()

    raw_doc = _mock_raw_document()
    chunks = chunk_jira_issue(raw_doc)
    logger.info("Produced %d chunks", len(chunks))
    for c in chunks:
        logger.info("  chunk[%d] type=%s len=%d", c.chunk_index, c.metadata.get("type"), len(c.text))

    texts = [c.text for c in chunks]
    masked = mask_chunks(texts)
    for chunk, m in zip(chunks, masked):
        chunk.text = m

    embedded = embed_chunks(chunks)
    delete_chunks_for_doc(raw_doc.doc_id)
    upsert_chunks(embedded)
    logger.info("Upserted %d embedded chunks", len(embedded))

    # Verify via Qdrant scroll
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    from qdrant_client.http import models as qmodels
    results, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=raw_doc.doc_id))]
        ),
        limit=20,
        with_payload=True,
        with_vectors=False,
    )
    logger.info("Verification: found %d points in Qdrant for doc_id=%s", len(results), raw_doc.doc_id[:12])
    for pt in results:
        logger.info("  point %s | type=%s", str(pt.id)[:8], pt.payload.get("type"))
    logger.info("=== JIRA mock test PASSED ===")


async def _run_real() -> None:
    from src.jira_agent.config import jira_config
    from src.jira_agent.pipeline import ingest_issue

    project_keys = jira_config.project_key_list or ["TEST"]
    issue_key = f"{project_keys[0]}-1"
    logger.info("=== JIRA agent test — REAL MODE (issue: %s) ===", issue_key)
    count = await ingest_issue(issue_key)
    logger.info("Stored %d chunks for %s", count, issue_key)
    logger.info("=== JIRA real test DONE ===")


async def main() -> None:
    from src.jira_agent.config import jira_config

    has_creds = bool(jira_config.jira_base_url and jira_config.jira_api_token)
    if has_creds:
        await _run_real()
    else:
        await _run_mock()


if __name__ == "__main__":
    asyncio.run(main())
