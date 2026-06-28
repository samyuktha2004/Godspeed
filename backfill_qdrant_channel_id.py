"""Backfill `channel_id` onto existing Qdrant points from Supabase `chunks.channel_id`.

Why this exists
---------------
`channel_id` was historically dropped before chunks reached Qdrant, so every point
ingested before that fix has no `channel_id` in its payload. Channel-level RBAC
(`doc_search` / `ticket_lookup` / `confluence_search`) therefore can't match those
points and they fall through the team-only fallback branch — i.e. existing data is
NOT channel-restricted. `rbac_migration.sql` backfilled `chunks.channel_id` in
Supabase but never touched Qdrant. This script closes that gap WITHOUT a full,
expensive re-ingest (no re-embedding) by copying `chunks.channel_id` onto the
matching Qdrant points.

Guarantees
----------
- **Correct point addressing:** reuses `ingestion.storage.qdrant_store._chunk_uuid`,
  the exact same `uuid5` derivation used at ingest, so we update the right points.
- **Merge, not overwrite:** `set_payload` sets only the `channel_id` key; vectors and
  all other payload fields are untouched.
- **Idempotent:** safe to run repeatedly.
- **Scoped + observable:** `--team`, `--dry-run`, `--verify`.

Usage
-----
    python backfill_qdrant_channel_id.py --dry-run            # preview, no writes
    python backfill_qdrant_channel_id.py                      # backfill all teams
    python backfill_qdrant_channel_id.py --team default       # one team only
    python backfill_qdrant_channel_id.py --verify             # backfill + report coverage

Connection settings are read from your normal config/env (SUPABASE_URL/KEY,
QDRANT_URL+QDRANT_API_KEY for cloud, or QDRANT_HOST/PORT for local).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_channel_id")

# Supabase PostgREST caps rows per response; page through with .range().
SUPABASE_PAGE = 1000
# Cap the number of point ids per set_payload call to keep requests reasonable.
SET_PAYLOAD_BATCH = 500


def _conf():
    """Return a getter that prefers src.config (has qdrant_url/api_key) then
    falls back to ingestion.config (has qdrant_collection)."""
    from ingestion.config import settings as ing
    try:
        from src.config import settings as app
    except Exception:
        app = None

    def get(name: str, default=None):
        if app is not None:
            val = getattr(app, name, None)
            if val:
                return val
        return getattr(ing, name, default)

    return get


def _supabase(get):
    from supabase import create_client

    url = get("supabase_url", "")
    key = get("supabase_key", "")
    if not url or not key:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        sys.exit(1)
    return create_client(url, key)


def _qdrant(get):
    from qdrant_client import QdrantClient

    url = get("qdrant_url", "")
    if url:
        logger.info("Connecting to Qdrant Cloud: %s", url)
        return QdrantClient(url=url, api_key=get("qdrant_api_key", "") or None)
    host = get("qdrant_host", "localhost")
    port = get("qdrant_port", 6333)
    logger.info("Connecting to local Qdrant: %s:%s", host, port)
    return QdrantClient(host=host, port=port)


def group_points_by_channel(rows: list[dict]) -> dict[str, list[str]]:
    """Map channel_id -> [qdrant point id, ...] for rows that carry a channel_id.

    Pure/testable: uses the same _chunk_uuid as ingestion so the point ids match.
    """
    from ingestion.storage.qdrant_store import _chunk_uuid

    by_channel: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        cid = r.get("channel_id")
        chunk_id = r.get("chunk_id")
        if not cid or not chunk_id:
            continue
        by_channel[cid].append(_chunk_uuid(chunk_id))
    return by_channel


def fetch_channel_rows(sb, team: str | None) -> list[dict]:
    """Page through Supabase chunks that have a non-null channel_id."""
    rows: list[dict] = []
    start = 0
    while True:
        q = (
            sb.table("chunks")
            .select("chunk_id, channel_id, team_id")
            .filter("channel_id", "not.is", "null")
        )
        if team:
            q = q.eq("team_id", team)
        try:
            res = q.range(start, start + SUPABASE_PAGE - 1).execute()
        except Exception:
            logger.exception(
                "Failed reading chunks.channel_id — has rbac_migration.sql been applied?"
            )
            sys.exit(1)
        page = res.data or []
        if not page:
            break
        rows.extend(page)
        logger.info("read %d chunks with channel_id...", len(rows))
        if len(page) < SUPABASE_PAGE:
            break
        start += SUPABASE_PAGE
    return rows


def apply_backfill(qc, collection: str, by_channel: dict[str, list[str]]) -> int:
    from qdrant_client.http.exceptions import UnexpectedResponse

    updated = 0
    for cid, ids in by_channel.items():
        channel_ok = 0
        for i in range(0, len(ids), SET_PAYLOAD_BATCH):
            batch = ids[i : i + SET_PAYLOAD_BATCH]
            try:
                qc.set_payload(
                    collection_name=collection,
                    payload={"channel_id": cid},
                    points=batch,
                    wait=True,
                )
                channel_ok += len(batch)
            except UnexpectedResponse:
                logger.exception("set_payload failed for channel %s (batch %d)", cid, i)
            except Exception:
                logger.exception("set_payload error for channel %s (batch %d)", cid, i)
        updated += channel_ok
        logger.info("channel %s: tagged %d/%d points", cid, channel_ok, len(ids))
    return updated


def verify_coverage(qc, collection: str) -> None:
    from qdrant_client.http import models as qm

    total = qc.count(collection_name=collection, exact=True).count
    null_cnt = qc.count(
        collection_name=collection,
        count_filter=qm.Filter(
            must=[qm.IsNullCondition(is_null=qm.PayloadField(key="channel_id"))]
        ),
        exact=True,
    ).count
    logger.info(
        "Coverage: %d total points | %d tagged with channel_id | %d still null "
        "(null = workspace-wide/untagged content, served via team fallback)",
        total, total - null_cnt, null_cnt,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Qdrant channel_id from Supabase chunks.")
    parser.add_argument("--team", help="Only backfill chunks for this team_id")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verify", action="store_true", help="Report channel_id coverage afterwards")
    args = parser.parse_args()

    get = _conf()
    collection = get("qdrant_collection", "knowledge_base")
    sb = _supabase(get)

    rows = fetch_channel_rows(sb, args.team)
    by_channel = group_points_by_channel(rows)
    logger.info(
        "Found %d chunks with channel_id across %d channel(s)%s",
        len(rows), len(by_channel), f" for team={args.team}" if args.team else "",
    )

    if not by_channel:
        logger.info("Nothing to backfill.")
        return

    if args.dry_run:
        for cid, ids in by_channel.items():
            logger.info("[dry-run] would set channel_id=%s on %d points", cid, len(ids))
        logger.info("[dry-run] no changes written.")
        return

    qc = _qdrant(get)
    updated = apply_backfill(qc, collection, by_channel)
    logger.info("Done — set channel_id on %d point(s) in collection %r", updated, collection)

    if args.verify:
        verify_coverage(qc, collection)


if __name__ == "__main__":
    main()
