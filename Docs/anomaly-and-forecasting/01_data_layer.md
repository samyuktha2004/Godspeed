# 01 · Data Layer — Time-Series Tables & Migration

---

## Why a New Data Layer?

Redis (`gs:queries`) caps history at 1,000 events. That is enough for a live dashboard but useless for anomaly detection, which requires:

- Hourly counts over a 14-day sliding window (≈ 336 rows per team)
- Per-day escalation rates over a 14-day comparison window
- Document age relative to query volume over 30 days
- Persistent anomaly signal records with resolution workflow

Three PostgreSQL tables are added in Supabase. No TimescaleDB extension is required — plain indexed `TIMESTAMPTZ` columns with a pre-aggregation function serve the access patterns needed.

---

## Migration File

**Path:** `supabase/anomaly_migration.sql`  
**Run after:** `rbac_migration.sql`  
**Idempotent:** Yes — all statements use `IF NOT EXISTS` / `ON CONFLICT DO UPDATE`

Apply via the Supabase dashboard SQL editor or:

```bash
supabase db push
# or
psql $DATABASE_URL -f supabase/anomaly_migration.sql
```

---

## Table 1: `query_events`

Persistent copy of every query event. Redis keeps the last 1,000; this table keeps the last 90 days (purged nightly by the staleness task).

```sql
CREATE TABLE IF NOT EXISTS query_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        text        NOT NULL UNIQUE,   -- same UUID as Redis event["id"]
    team_id         text        NOT NULL,
    session_id      text,
    success         boolean     NOT NULL DEFAULT true,
    duration_ms     integer,
    escalated       boolean     NOT NULL DEFAULT false,
    guardrail_score float,
    agent_metrics   jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);
```

| Column | Source | Notes |
|---|---|---|
| `event_id` | `agent/api.py` event `"id"` field | Used for idempotent upsert — Redis replays are safe |
| `team_id` | Server-enforced from session | Never trusted from client |
| `escalated` | `guardrail_score < 0.5` flag | Primary input for escalation trend detection |
| `agent_metrics` | `event["agents"]` dict | `{"doc_search": {"chunk_count": 5, "confidence": "high"}}` |

**Indexes:**
- `(team_id, created_at DESC)` — primary scan for per-team time ranges
- `(created_at DESC)` — global purge query
- `(team_id, escalated, created_at DESC)` — escalation rate aggregation

**Write path:** `agent/api.py` → `asyncio.ensure_future(async_upsert_query_event(event))` — fire-and-forget, never blocks SSE stream.

---

## Table 2: `query_events_hourly`

Pre-aggregated hourly buckets. The Z-score detection task reads this table, not `query_events` directly, to avoid shipping thousands of raw rows to the Celery worker.

```sql
CREATE TABLE IF NOT EXISTS query_events_hourly (
    team_id          text        NOT NULL,
    hour_bucket      timestamptz NOT NULL,     -- truncated to the hour, UTC
    query_count      integer     NOT NULL DEFAULT 0,
    escalation_count integer     NOT NULL DEFAULT 0,
    avg_duration_ms  integer,
    PRIMARY KEY (team_id, hour_bucket)
);
```

**Index:** `(team_id, hour_bucket DESC)` — range scan for last N days.

**Write path:** The `aggregate_hourly_bucket` PostgreSQL function (see below) is called via Supabase RPC. The function does the aggregation inside the database — no rows are shipped to Python.

---

## Table 3: `anomaly_signals`

Every detected anomaly is a row here. The frontend Anomalies tab reads from this table via the API.

```sql
CREATE TABLE IF NOT EXISTS anomaly_signals (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id      text,
    signal_type  text        NOT NULL,
    entity_type  text,
    entity_id    text,
    severity     text        NOT NULL DEFAULT 'medium',
    score        float       NOT NULL DEFAULT 0.0,
    details      jsonb       NOT NULL DEFAULT '{}',
    resolved     boolean     NOT NULL DEFAULT false,
    resolved_by  uuid        REFERENCES users(id),
    resolved_at  timestamptz,
    detected_at  timestamptz NOT NULL DEFAULT now()
);
```

### `signal_type` Values

| Value | Produced By | `entity_type` | `score` Meaning |
|---|---|---|---|
| `query_spike` | Z-score task | `Team` | Z-score value (e.g. 4.2) |
| `query_drop` | Z-score task | `Team` | Z-score value (negative, e.g. −2.8) |
| `escalation_trend` | Z-score task | `Team` | Rate ratio (e.g. 1.8 = 80% worse) |
| `staleness` | Staleness task | `Document` | Staleness risk 0.0–1.0 |
| `dependency_risk` | Dep risk task | `Library` | Composite risk score 0.0–1.0 |

### `severity` Values

| Value | Trigger |
|---|---|
| `critical` | query_spike: \|Z\| ≥ 5.0 · staleness: ≥ 0.8 · dep_risk: ≥ 0.7 |
| `high` | query_spike: \|Z\| ≥ 4.0 · staleness: ≥ 0.6 · dep_risk: ≥ 0.5 |
| `medium` | query_spike: \|Z\| ≥ 3.5 · staleness: ≥ 0.3 · dep_risk: ≥ 0.3 |
| `low` | Everything else above detection threshold |

### `details` JSONB Shapes

**query_spike / query_drop:**
```json
{
  "z_score": 4.2,
  "current_count": 87,
  "baseline_mean": 23.4,
  "baseline_stdev": 15.1,
  "hour_bucket": "2026-05-17T14:00:00",
  "window_hours": 335
}
```

**escalation_trend:**
```json
{
  "ratio": 1.92,
  "current_rate": 0.192,
  "prior_rate": 0.1,
  "current_total_queries": 52,
  "prior_total_queries": 60
}
```

**staleness:**
```json
{
  "title": "Kubernetes Ingress Setup Guide",
  "age_days": 240,
  "age_factor": 0.9306,
  "query_pressure": 0.72,
  "updated_at": "2025-09-20T10:00:00"
}
```

**dependency_risk:**
```json
{
  "library_name": "fastapi",
  "current_version": "0.95.0",
  "latest_version": "0.115.0",
  "version_lag": 1.0,
  "downstream_count": 8,
  "downstream_normalized": 0.62,
  "incident_count": 2,
  "incident_rate": 0.0055,
  "poisson_30d": 0.153
}
```

**Indexes:**
- `(team_id, signal_type, detected_at DESC)` — filtered list queries
- `(severity, resolved, detected_at DESC)` — severity-sorted alert feed
- `(resolved, team_id, detected_at DESC)` — active signals per team
- `(entity_type, entity_id)` — entity-specific lookups

**Deduplication:** `db.insert_signal()` checks for an identical unresolved signal for the same `(signal_type, team_id, entity_id)` in the last 2 hours before inserting, preventing the 15-minute task from creating redundant rows.

---

## PostgreSQL Aggregation Function

`aggregate_hourly_bucket` runs inside the database, keeping the aggregation logic server-side.

```sql
CREATE OR REPLACE FUNCTION aggregate_hourly_bucket(p_team_id text, p_hour timestamptz)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO query_events_hourly
           (team_id, hour_bucket, query_count, escalation_count, avg_duration_ms)
    SELECT  p_team_id, p_hour,
            count(*)::integer,
            count(*) FILTER (WHERE escalated = true)::integer,
            avg(duration_ms)::integer
    FROM    query_events
    WHERE   team_id = p_team_id
      AND   date_trunc('hour', created_at AT TIME ZONE 'UTC') = p_hour
    ON CONFLICT (team_id, hour_bucket) DO UPDATE
        SET query_count      = EXCLUDED.query_count,
            escalation_count = EXCLUDED.escalation_count,
            avg_duration_ms  = EXCLUDED.avg_duration_ms;
END;
$$;
```

**Called via Supabase RPC:**
```python
_sb().rpc("aggregate_hourly_bucket", {
    "p_team_id": team_id,
    "p_hour":    hour_bucket,
}).execute()
```

---

## Data Persistence Layer: `src/anomaly/db.py`

All Supabase reads and writes go through this module. Every function is wrapped in `try/except` — callers never crash if Supabase is unavailable.

### Key Functions

| Function | Direction | Called By |
|---|---|---|
| `upsert_query_event(event)` | Write | `agent/api.py` (sync, via executor) |
| `async_upsert_query_event(event)` | Write | `agent/api.py` (async shim) |
| `aggregate_hourly(team_id, hour)` | Write | Future: aggregation task |
| `get_hourly_counts(team_id, days)` | Read | `tasks.run_zscore_anomaly_detection` |
| `get_all_team_ids()` | Read | `tasks.run_zscore_anomaly_detection` |
| `insert_signal(...)` | Write | All three detection algorithms |
| `get_signals(team_id, ...)` | Read | `router.list_signals` |
| `resolve_signal(id, user_id)` | Write | `router.resolve_signal` |
| `get_signals_summary()` | Read | `router.signals_summary` |
| `get_staleness_top(limit)` | Read | `router.staleness_list` |
| `get_dependency_risk(limit)` | Read | `router.dependency_risk` |
| `purge_old_events()` | Write | `tasks.run_staleness_scoring` (nightly) |

---

## 90-Day Event Purge

`purge_old_events()` runs at the end of every `compute_staleness_scores` Celery task (daily 03:00 UTC):

```python
_sb().table("query_events").delete().lt("created_at", cutoff).execute()
```

This keeps the `query_events` table bounded. At 1 query/minute per team, 90 days = ~129,600 rows per team — manageable for PostgreSQL without partitioning.
