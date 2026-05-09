"""
File agent runthrough.

Creates sample files (CSV, TXT, HTML) in a temp directory, processes them
through the full pipeline (detect → parse → chunk → PII mask → embed → Qdrant),
then verifies the stored vectors via Qdrant scroll.

Run:
  python -m src.file_agent.test_run
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("file_test_run")

_SAMPLE_CSV = """Name,Role,Email,Phone
Alice Smith,Engineer,alice@example.com,555-111-2222
Bob Jones,Manager,bob@example.com,555-333-4444
Carol White,Designer,carol@example.com,555-555-6666
"""

_SAMPLE_TXT = """Engineering Onboarding Guide

Welcome to the engineering team. Your first point of contact is your manager, Alice Smith (alice@example.com).

Repository access:
- Clone the main repo from GitHub
- Set up your SSH key and add it to your profile
- Run `make dev` to start the local environment

The on-call rotation is managed via PagerDuty. Contact the SRE team for access.
"""

_SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>System Architecture</title></head>
<body>
<h1>System Architecture</h1>
<p>The backend runs on Kubernetes. All secrets are managed by Vault. Contact admin@example.com for access.</p>
<h2>Services</h2>
<p>The API gateway handles all external traffic. Internal services communicate via gRPC.</p>
<table>
  <tr><th>Service</th><th>Port</th><th>Team</th></tr>
  <tr><td>auth-service</td><td>8080</td><td>Platform</td></tr>
  <tr><td>data-service</td><td>8081</td><td>Data</td></tr>
</table>
<h2>Deployment</h2>
<p>Deploy via GitHub Actions. Each PR triggers a staging deploy automatically.</p>
</body>
</html>
"""


def _write_samples(tmpdir: str) -> list[str]:
    files = []
    for name, content in [
        ("onboarding.csv", _SAMPLE_CSV),
        ("guide.txt", _SAMPLE_TXT),
        ("architecture.html", _SAMPLE_HTML),
    ]:
        path = os.path.join(tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        files.append(path)
    return files


def main() -> None:
    from ingestion.storage.qdrant_store import ensure_collection_exists
    from src.file_agent.pipeline import process_file
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    from ingestion.config import settings

    logger.info("=== File agent test ===")
    ensure_collection_exists()

    with tempfile.TemporaryDirectory() as tmpdir:
        files = _write_samples(tmpdir)
        total_chunks = 0

        for file_path in files:
            fname = Path(file_path).name
            count = process_file(file_path, team_id="test_team")
            logger.info("Processed %s → %d chunks", fname, count)
            total_chunks += count

            # Verify in Qdrant
            doc_id = hashlib.sha256(f"file:{fname}".encode()).hexdigest()
            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
            results, _ = client.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))]
                ),
                limit=50,
                with_payload=True,
                with_vectors=False,
            )
            logger.info(
                "  Qdrant verification: %d points for %s (doc_id=%s...)",
                len(results),
                fname,
                doc_id[:12],
            )
            for pt in results[:3]:
                logger.info("    point %s | type=%s", str(pt.id)[:8], pt.payload.get("block_type"))

    logger.info("=== File agent test DONE — total chunks: %d ===", total_chunks)


if __name__ == "__main__":
    main()
