# 03 — Retrieval Scaling (BM25 flag + Qdrant payload indexes)

> **Status: Implemented & unit-verified (9/9).** Removes the per-ingest BM25 rebuild bottleneck and a tenant leak; adds index-backed filtered search. Default retrieval is now dense + BGE-M3 sparse.

---

## Why BM25 (`rank_bm25`) was a liability

The third retrieval leg used `rank_bm25` — a dev-grade, in-memory library. It had three problems:

1. **Full rebuild per ingest.** `ingest_job` called `rebuild_from_supabase()` on every ingest, re-reading and re-tokenizing the **entire** corpus into one global `data/bm25_index.pkl`. O(corpus) cost for editing one file.
2. **Stale index.** `doc_search._load_bm25` cached the index in a module singleton that **never reloaded** — a running agent served the old index until restart.
3. **RBAC/tenant leak.** BM25 scored the global corpus with **no team/channel filter** (`get_all_chunks` doesn't even store `team_id`), and BM25-only hits were reconstructed **bypassing** the RBAC filter — a cross-tenant leak.

### Why Qdrant sparse is the right replacement

BGE-M3's **sparse** vectors are a learned, BM25-equivalent lexical signal that is already stored and queried in Qdrant — through the *same* RBAC `query_filter` as dense. Unlike `rank_bm25`, the sparse vector lives in an inverted index that is on-disk-capable, shardable, and scales sub-linearly. The "real BM25 at scale" alternative would be a dedicated OpenSearch/Elasticsearch tier — new infra, against this project's zero-infra design.

**Decision:** gate `rank_bm25` behind a **default-OFF flag** (ship dense+sparse, keep BM25 one toggle away for a future labeled A/B), and make even the retained flag-on path **tenant-safe**.

---

## What changed

### Config — `agent/config.py` + `ingestion/config.py`

```python
enable_bm25: bool = False          # both configs (env: ENABLE_BM25)
qdrant_sparse_on_disk: bool = False # ingestion config (env: QDRANT_SPARSE_ON_DISK)
```

### Query side — `agent/tools/doc_search.py`

- **Flag OFF (default):** `_load_bm25()` is never called; RRF fuses only `[dense, sparse]`; reranker unchanged.
- **Flag ON:** BM25 contributes ranking, **but the leaky BM25-only reconstruction was removed.** Any id not present in the RBAC-filtered Qdrant candidate set is dropped — so BM25 can only *re-rank points the user is already allowed to see*. It can never introduce an unfiltered cross-tenant hit.
  - *Tradeoff:* the flag-on path loses BM25-only recall. A fully faithful BM25 A/B would require indexing `team_id`/`channel_id` — tracked in [`Docs/TODO.md`](../TODO.md) under "Retrieval scaling".

### Ingest side — `ingestion/jobs/ingest_job.py`

`rebuild_from_supabase()` is now gated:

```python
if settings.enable_bm25:
    rebuild_from_supabase()
```

Default OFF ⇒ the per-ingest full rebuild is gone; ingest cost no longer scales with total corpus size. The Phase-1 manifest refresh still runs unconditionally.

### Qdrant scale hygiene — `ingestion/storage/qdrant_store.py`

- **Payload indexes:** new idempotent `ensure_payload_indexes()` creates keyword indexes on `team_id`, `channel_id`, `source_type`, `space_key`, `repo`, `doc_id`. It runs once per process (`_indexes_ensured` guard), wraps each `create_payload_index` in try/except (already-exists is a no-op), and is called from the `upsert_chunks` path. Qdrant builds each index over existing points, so this also benefits current data. These directly accelerate the RBAC filter **and** the Phase-1 routing scope filters.
- **On-disk sparse:** `qdrant_sparse_on_disk` (default OFF) is applied to `SparseIndexParams(on_disk=...)` at collection creation. **Only affects newly-created collections** — an existing collection must be migrated/recreated to change it.

---

## Retained, not deleted

`rank_bm25`, `ingestion/storage/bm25_store.py`, and `get_all_chunks` remain in place for the flag-on path and easy rollback. Re-enabling is a one-env-var change (`ENABLE_BM25=true` in **both** the agent and ingestion environments). The stale-singleton issue (#2 above) is left as-is on the flag-on path and is only relevant when BM25 is explicitly re-enabled.

---

## Default retrieval after this change

```
query → BGE-M3 (dense + sparse) → 2 Qdrant queries (RBAC-filtered) → RRF fusion → BGE reranker → top-K
```

BM25 is an optional third leg, off by default.

---

## Verified behavior (isolated tests, real `run_doc_search`)

- **OFF:** `_load_bm25` not called; results come from Qdrant only; no BM25-only id appears.
- **ON:** BM25 runs, but a BM25-only id with no RBAC payload is dropped; results stay a subset of the RBAC-filtered Qdrant set.
- **Indexes:** all six fields attempted once; a second call no-ops (idempotent); a per-field error is swallowed.
