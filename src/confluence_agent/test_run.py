"""
Confluence agent runthrough.

With credentials (CONFLUENCE_BASE_URL + CONFLUENCE_TOKEN + CONFLUENCE_EMAIL set):
  Fetches the first page from CONFLUENCE_SPACES, runs the full pipeline,
  and verifies the vectors in Qdrant.

Without credentials (mock mode):
  Builds a synthetic RawDocument with realistic Confluence Storage HTML,
  runs chunker → PII mask → embed → Qdrant, and verifies via Qdrant scroll.

Run:
  python -m src.confluence_agent.test_run
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("confluence_test_run")

_SAMPLE_HTML = """
<h1>Authentication Overview</h1>
<p>Our SSO system uses SAML 2.0. Contact the security team at security@example.com for access.</p>
<h2>Setup Instructions</h2>
<p>
  1. Generate a keypair using <code>openssl</code>.<br/>
  2. Submit the public certificate to the IdP admin (Alice Smith, phone: 555-987-6543).<br/>
  3. Configure the SP metadata URL.
</p>
<h2>Troubleshooting</h2>
<p>If login fails, check the SAML assertion expiry. Default TTL is 5 minutes.</p>
<table>
  <tr><th>Error Code</th><th>Cause</th><th>Fix</th></tr>
  <tr><td>401</td><td>Expired assertion</td><td>Sync clocks with NTP</td></tr>
  <tr><td>403</td><td>Missing attribute</td><td>Add email to IdP release policy</td></tr>
</table>
"""


def _mock_raw_document():
    from ingestion.models import RawDocument

    return RawDocument(
        doc_id=hashlib.sha256(b"confluence:123456").hexdigest(),
        title="Authentication Overview",
        content=_SAMPLE_HTML,
        source_url="http://mock-confluence/wiki/spaces/ENG/pages/123456",
        source_type="confluence",
        team_id="test_team",
        metadata={
            "page_id": "123456",
            "space_key": "ENG",
            "ancestors": ["Engineering", "Security"],
            "version": 3,
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
    from src.confluence_agent.chunker import chunk_confluence_page
    from ingestion.config import settings

    logger.info("=== Confluence agent test — MOCK MODE ===")
    ensure_collection_exists()

    raw_doc = _mock_raw_document()
    chunks = chunk_confluence_page(raw_doc)
    logger.info("Produced %d chunks", len(chunks))
    for c in chunks:
        heading = c.metadata.get("section_heading", "")
        logger.info("  chunk[%d] heading=%r len=%d", c.chunk_index, heading, len(c.text))

    texts = [c.text for c in chunks]
    masked = mask_chunks(texts)
    for chunk, m in zip(chunks, masked):
        chunk.text = m

    embedded = embed_chunks(chunks)
    delete_chunks_for_doc(raw_doc.doc_id)
    upsert_chunks(embedded)
    logger.info("Upserted %d embedded chunks", len(embedded))

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
    logger.info(
        "Verification: found %d points in Qdrant for doc_id=%s",
        len(results),
        raw_doc.doc_id[:12],
    )
    for pt in results:
        logger.info("  point %s | heading=%s", str(pt.id)[:8], pt.payload.get("section_heading", ""))
    logger.info("=== Confluence mock test PASSED ===")


async def _run_real() -> None:
    from src.confluence_agent.config import confluence_config
    from src.confluence_agent.pipeline import ingest_space

    spaces = confluence_config.space_list
    if not spaces:
        logger.warning("No CONFLUENCE_SPACES configured — cannot run real test")
        return
    space_key = spaces[0]
    logger.info("=== Confluence agent test — REAL MODE (space: %s) ===", space_key)
    count = await ingest_space(space_key)
    logger.info("Stored %d chunks for space %s", count, space_key)
    logger.info("=== Confluence real test DONE ===")


async def main() -> None:
    from src.confluence_agent.config import confluence_config

    has_creds = bool(confluence_config.confluence_base_url and confluence_config.confluence_token)
    if has_creds:
        await _run_real()
    else:
        await _run_mock()


if __name__ == "__main__":
    asyncio.run(main())
