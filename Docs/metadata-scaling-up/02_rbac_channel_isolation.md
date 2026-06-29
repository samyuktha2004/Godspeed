# 02 — RBAC Channel Isolation Fix

> **Status: Implemented & unit-verified (12/12).** Closes a channel-level access-control hole across the entire retrieval path. Includes a backfill script for existing data.

---

## The problem (what was broken)

The RBAC model is sound up to retrieval: login resolves a user's channel UUIDs (`src/auth/db.py:get_allowed_channel_ids`), the session stores them, and `POST /agent/query` injects them server-side (admins get `[]` = bypass). Ingestion even plumbs `channel_id` from the API request down to each chunk. But it broke downstream in two ways:

1. **`channel_id` was dropped before Qdrant.** `embed_chunks` built `EmbeddedChunk` without copying `channel_id`, and `qdrant_store.upsert_chunks` didn't write it to the payload. Result: **every** point had no `channel_id`, so the channel-match branch in the retrieval filter matched nothing and everything fell through the team-only fallback — channel RBAC was a **silent no-op**.
2. **Two agents bypassed channels entirely.** `ticket_lookup` and `confluence_search` filtered on `team_id` only and never even received `allowed_channel_ids`. Even after fixing #1, a user could pull Jira/Confluence chunks from channels they can't access by routing through those agents.

---

## The fix (all stages)

| Stage | File | Change |
|---|---|---|
| Embed | `ingestion/pipeline/embedder.py` | Carry `channel_id` onto `EmbeddedChunk` |
| Store | `ingestion/storage/qdrant_store.py` | Write `channel_id` into the Qdrant payload |
| Filter | `agent/tools/doc_search.py` | New shared `build_rbac_filter(team_id, allowed_channel_ids)` — single source of truth |
| Agents | `agent/tools/ticket_lookup.py`, `confluence_search.py` | Accept `allowed_channel_ids`; pin `source_type`, then AND the shared RBAC filter |
| Wiring | `agent/graph.py` | Pass `allowed_channel_ids` into the ticket_lookup + confluence nodes |

### The shared filter — `build_rbac_filter`

```python
def build_rbac_filter(team_id, allowed_channel_ids):
    if allowed_channel_ids:
        # match an allowed channel, OR legacy/workspace-wide chunks with no channel_id
        return Filter(should=[
            FieldCondition(key="channel_id", match=MatchAny(any=allowed_channel_ids)),
            Filter(must=[
                FieldCondition(key="team_id", match=MatchValue(value=team_id)),
                IsNullCondition(is_null=PayloadField(key="channel_id")),
            ]),
        ])
    # admins / callers with no channel scoping → team-only
    return Filter(must=[FieldCondition(key="team_id", match=MatchValue(value=team_id))])
```

Centralising it means `doc_search`, `ticket_lookup`, and `confluence_search` **cannot drift apart** — a per-agent copy was exactly what let two agents bypass channels. The Phase-1 routing scope is ANDed *on top* of this filter, never replacing it.

### Behavior

- **Channel-scoped user:** sees chunks in their allowed channels, plus legacy/workspace-wide chunks that have no `channel_id` (team match).
- **Admin (`allowed_channel_ids = []`):** team-only filter — full knowledge base, by design.

---

## Deliberately out of scope (flagged, not silently changed)

- **`sql_query`** stays team-scoped. Its NL-to-SQL contract enforces `team_id` via a single placeholder; channel-filtering aggregate counts would require reworking that contract. It returns stats, not document bodies — lower risk.
- **`slack_search`** hits the live Slack API and is governed by *bot membership*; its `allowed_channel_ids` are internal RBAC UUIDs, a different namespace. Not a Qdrant RBAC path.

---

## Migrating existing data — `backfill_qdrant_channel_id.py`

The fix makes **new** ingests channel-tagged. **Existing** Qdrant points (ingested before the fix) still have no `channel_id` and keep falling through the team-only fallback until re-tagged. `rbac_migration.sql` backfilled `chunks.channel_id` in Supabase but never touched Qdrant — this script closes that gap **without re-embedding**.

What it does:
- Pages through `chunks` in Supabase where `channel_id` is not null.
- Groups chunk → Qdrant point id by channel, reusing `qdrant_store._chunk_uuid` (the *exact* `uuid5(NAMESPACE_DNS, chunk_id)` derivation used at ingest — so it targets the right points).
- `set_payload`s `channel_id` onto those points (merge only — vectors and other fields untouched). Idempotent.

Usage:

```bash
python backfill_qdrant_channel_id.py --dry-run            # preview, no writes
python backfill_qdrant_channel_id.py --team default       # scope to one team
python backfill_qdrant_channel_id.py --verify             # backfill + coverage report
```

`--verify` reports e.g. `12000 total points | 11800 tagged | 200 still null`. Remaining `null` points are legitimately untagged content (no channel was ever assigned) and are served via the team fallback by design.

> **Note:** Content that was never assigned a `channel_id` at ingest stays team-scoped until ingested with one. Enforcing channels on such content requires assigning it a channel (via the ingest API's `channel_id`) and re-ingesting, or updating `chunks.channel_id` in Supabase and re-running the backfill.

---

## Verified behavior (isolated tests, real code)

- channel mode → OR filter (channel `MatchAny` + legacy team/null branch); no-channel/admin → team-only.
- `ticket_lookup` and `confluence_search` both accept `allowed_channel_ids` and call `build_rbac_filter`; neither hand-rolls a team-only filter anymore.
- backfill grouping produces point ids identical to `_chunk_uuid` and skips null channel/chunk ids.
