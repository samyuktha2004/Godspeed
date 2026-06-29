# Metadata Scaling-Up — Route-then-Retrieve, RBAC Isolation & Retrieval Scaling

> **Status: Implemented & unit-verified** on branch `Metadata-scaling-up`.
> Logic, wiring, and definitions verified (43 isolated checks + static analysis); live end-to-end smoke test requires the running stack (see [04_config_and_operations.md](04_config_and_operations.md)).

---

## Why this exists

The original concern: *"reading and embedding across the entire database for every query will be very expensive as we scale."* Investigation showed the per-query vector cost is **not** the problem — embeddings are computed once at ingest and Qdrant does a sub-linear HNSW search. The real costs and risks that scaling exposes were:

1. **Wasteful fan-out** — the planner could fire up to 6 retrieval agents per query regardless of what the query actually needs.
2. **A per-ingest full BM25 rebuild** — every single-file ingest re-read and re-tokenized the *entire* corpus into one global pickle.
3. **A silent RBAC hole** — `channel_id` never reached Qdrant, so channel-level access control was effectively a no-op, and two agents bypassed it entirely.

This work delivers a **two-stage "route-then-retrieve" layer** (the user's "metadata gist that points to sources" idea), a **complete RBAC channel fix**, and **retrieval scaling hygiene** — without changing the core dense+sparse+rerank retrieval path.

---

## The three workstreams

| Area | What it does | Doc |
|---|---|---|
| **Query routing** | A deterministic `router_node` narrows scope + prunes agents before the LLM planner, driven by a cheap per-team "knowledge manifest". | [01_query_routing_layer.md](01_query_routing_layer.md) |
| **RBAC channel isolation** | Carries `channel_id` end-to-end into Qdrant and enforces one shared team/channel filter across all retrieval agents. Includes a backfill script for existing data. | [02_rbac_channel_isolation.md](02_rbac_channel_isolation.md) |
| **Retrieval scaling** | Default-OFF flag for the dev-grade BM25 leg (kills the rebuild bottleneck + a tenant leak) and Qdrant payload indexes for fast filtered search. | [03_retrieval_scaling.md](03_retrieval_scaling.md) |
| **Config & operations** | New config flags, the Supabase migration, the backfill runbook, and the smoke-test procedure. | [04_config_and_operations.md](04_config_and_operations.md) |

---

## Pipeline at a glance (after these changes)

```
POST /agent/query
  ↓
router_node        ← NEW · deterministic · loads team manifest, applies cheap rules
  ↓                  emits RoutingDecision{scope, suggested_agents, confidence}
  ↓                  → SSE: routing_ready
planner_node       ← receives manifest digest + RoutingDecision; prefers suggestions
  ↓                  → SSE: plan_ready
[retrieval nodes]  ← doc_search ∥ ticket_lookup ∥ confluence_search ∥ slack ∥ sql ∥ live
  ↓                  · shared RBAC filter (team + channel) on every Qdrant agent
  ↓                  · optional routing scope ANDed on (high-confidence only)
  ↓                  · BM25 leg is opt-in; default = dense + BGE-M3 sparse
join → synthesiser → guardrail → END
```

**Design invariants preserved**
- **Core retrieval unchanged:** BGE-M3 dense + sparse → RRF → BGE reranker. Routing only adds a *pre-filter* and prunes which agents fire.
- **Soft routing:** a narrowing scope is emitted *only* at high confidence; otherwise the search stays broad — a correct answer can never become unreachable.
- **Fail-safe ingest:** manifest refresh and payload-index creation are best-effort and never break an ingest.

---

## Key files changed

| File | Role |
|---|---|
| `agent/agents/router.py` | **NEW** — deterministic router + Redis-cached manifest read |
| `agent/models.py` | `RetrievalScope`, `RoutingDecision`; `KnowledgeGraphState.routing_decision` |
| `agent/graph.py` | `router_node` entry point; threads scope + `allowed_channel_ids` into agents |
| `agent/agents/planner.py`, `agent/prompts.py` | Planner consumes routing decision + manifest digest |
| `agent/tools/doc_search.py` | `build_rbac_filter`, `build_scope_conditions`; BM25 gated behind flag |
| `agent/tools/ticket_lookup.py`, `confluence_search.py` | Use shared RBAC filter + scope |
| `ingestion/storage/manifest_store.py` | **NEW** — manifest build/read/update + cache bust |
| `ingestion/jobs/ingest_job.py` | Manifest refresh on ingest; BM25 rebuild gated |
| `ingestion/jobs/cag_job.py` | Nightly per-space/repo gist generation |
| `ingestion/pipeline/embedder.py`, `ingestion/storage/qdrant_store.py` | Carry `channel_id` to payload; payload indexes; on-disk flag |
| `agent/config.py`, `ingestion/config.py` | `enable_bm25`, `qdrant_sparse_on_disk` |
| `supabase/schema.sql` | `teams.routing_manifest`, `teams.manifest_at` |
| `backfill_qdrant_channel_id.py` | **NEW** — one-off backfill of `channel_id` onto existing points |
