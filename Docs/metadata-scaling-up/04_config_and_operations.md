# 04 — Config, Migration & Operations

> **Status: Implemented.** Everything needed to configure, migrate, and verify the changes in 01–03.

---

## New configuration

| Setting | Env var | Default | Where read | Purpose |
|---|---|---|---|---|
| `enable_bm25` | `ENABLE_BM25` | `false` | `agent/config.py` **and** `ingestion/config.py` | Opt-in BM25 third leg. Off ⇒ dense+sparse only, no per-ingest rebuild. Set in **both** the agent and worker environments. |
| `qdrant_sparse_on_disk` | `QDRANT_SPARSE_ON_DISK` | `false` | `ingestion/config.py` | Persist the sparse index on disk. **Only applied at collection creation.** |

No new required keys — existing `GOOGLE_API_KEY`, `SUPABASE_URL/KEY`, `QDRANT_*`, `REDIS_URL` are unchanged.

---

## Database migration (Supabase)

The routing manifest needs two columns on `teams`. They are in `supabase/schema.sql`; for an existing database run:

```sql
alter table teams add column if not exists routing_manifest jsonb;
alter table teams add column if not exists manifest_at      timestamptz;
```

(`ALTER` is DDL → "Success. No rows returned" is the expected output.) Verify with `\d teams` — you should see `routing_manifest | jsonb` and `manifest_at | timestamp with time zone`.

No other schema changes. `channel_id` columns on `documents`/`chunks` already exist from `rbac_migration.sql`.

---

## Qdrant payload indexes

Created automatically on the next ingest (first `upsert_chunks` per process) by `ensure_payload_indexes()`. They build over existing points too — **no manual step required**. To confirm, inspect the collection (`GET /collections/knowledge_base`) and look for payload schema on `team_id`, `channel_id`, `source_type`, `space_key`, `repo`, `doc_id`.

---

## Backfilling channel_id onto existing Qdrant points

Required only if you had data ingested **before** the RBAC fix and want channel RBAC enforced on it. See [02_rbac_channel_isolation.md](02_rbac_channel_isolation.md). Quick reference:

```bash
python backfill_qdrant_channel_id.py --dry-run     # preview
python backfill_qdrant_channel_id.py --verify      # backfill + coverage report
```

Idempotent; honors local (`QDRANT_HOST/PORT`) or cloud (`QDRANT_URL/QDRANT_API_KEY`) automatically.

---

## How the manifest gets populated

- **On every ingest:** `refresh_manifest_structure(team_id)` updates counts + which spaces/repos/projects exist (no LLM). A team's manifest goes from `null` to populated after its first post-change ingest.
- **Nightly (CAG job, ~02:00 UTC):** `_refresh_team_manifest` regenerates the per-entity `gist` text via Gemini.

Until a manifest exists, the router degrades gracefully to ticket-id/keyword signals.

---

## Smoke-test runbook

Requires **Docker Desktop + a Gemini API key + a Supabase project** (both free-tier). Docker alone is not sufficient: the planner/synthesiser call Gemini, and ingestion/RBAC/manifest persist to Supabase (not in `docker-compose.yml`).

1. `cp .env.example .env`; set `GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (other source keys optional).
2. Apply Supabase SQL: `schema.sql` → `rbac_migration.sql` → the two manifest `ALTER`s above.
3. `docker compose up --build` (first build downloads BGE-M3/GLiNER/reranker — ~2–3 GB, needs ~8 GB RAM).
4. Run the checks via the UI at `http://localhost:8000` (login `demo`/`demo`) or curl:

| Check | Expectation |
|---|---|
| `GET /health` | Redis / Qdrant / Neo4j all ok |
| Ingest a PDF | Worker logs show `ensured payload indexes on team_id, channel_id, …`; **no** `BM25 rebuilt …` line (BM25 off) |
| `select team_id, routing_manifest from teams;` | Manifest populated with counts |
| `POST /agent/query` (SSE) | `routing_ready` arrives **before** `plan_ready` |
| Query a ticket id / known space | Fewer `agent_started` events than a vague query (fan-out pruned) |

---

## Verification status

All logic, wiring, and definitions are verified by isolated tests + static analysis (run against the post-merge tree):

| Suite | Checks |
|---|---|
| Router decision logic | 7/7 |
| Manifest builder | 10/10 |
| RBAC filter + agent enforcement | 12/12 |
| Backfill point-ID derivation | 5/5 |
| Phase 2 BM25 flag + payload indexes | 9/9 |
| **Total** | **43/43** |

Plus: `pyflakes` reports **no undefined names / broken references** across all changed files, and every file compiles. Live I/O (Gemini/Qdrant/Supabase round-trips) is the only thing not exercisable without the running stack — covered by the smoke-test runbook above.

---

## Deferred (documented, not built)

Tracked centrally in [`Docs/TODO.md`](../TODO.md) under "Backend — Not Yet Built (Future Candidates) → Retrieval scaling".
