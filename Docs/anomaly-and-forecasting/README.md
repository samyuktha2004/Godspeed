# Area 4 — Anomaly Detection & Forecasting

> **Status: Implemented** on branch `anomaly-and-forecasting`.  
> Previously marked "Planned Extension" in `03_analytics_and_intelligence.md`.

---

## What This Area Does

Area 4 consumes the raw event streams produced by Areas 1–3 and adds a detection and forecasting layer on top. It answers questions that static dashboards cannot:

- Is this query spike normal, or did something break?
- Which documents are dangerously stale *and* heavily queried?
- Is our escalation rate trending worse or better?
- Which library is most likely to cause an incident in the next 30 days?

None of this required new data pipelines. All signals already existed in Redis, Supabase, and Neo4j — Area 4 adds the time-series persistence and mathematical models to make them actionable.

---

## Document Map

| File | Contents |
|---|---|
| [`01_data_layer.md`](./01_data_layer.md) | Three new Supabase tables, PostgreSQL function, migration guide, data flow |
| [`02_detection_algorithms.md`](./02_detection_algorithms.md) | Z-score spike detection, escalation trend, staleness scoring, dependency risk + Poisson model |
| [`03_api_reference.md`](./03_api_reference.md) | All six `/api/anomaly` endpoints with request/response shapes |
| [`04_jobs_and_scheduling.md`](./04_jobs_and_scheduling.md) | Celery Beat schedule, task configuration, manual trigger guide |

---

## File Map (Implementation)

```
supabase/
  anomaly_migration.sql           ← Run first: 3 tables + aggregate function

src/anomaly/
  __init__.py
  db.py                           ← All Supabase reads/writes
  tasks.py                        ← Detection algorithms (stdlib only)
  router.py                       ← FastAPI /api/anomaly endpoints
  notifier.py                     ← In-process WebSocket broadcast bridge

agent/api.py                      ← +7 lines: fire-and-forget event persist
src/celery_app.py                 ← poll_metrics_anomalies implemented;
                                     2 new daily tasks added
main.py                           ← anomaly_router registered
```

---

## How It Fits Into the Five-Area System

```
Area 1 (RAG)          → query retrieval confidence feeds staleness pressure signal
Area 2 (Pipelines)    → document updated_at feeds staleness age factor
Area 3 (Analytics)    → query events → query_events table → Z-score + trend models
                        escalation events → escalation_trend detection
                        Neo4j graph → dependency risk model

Area 4 (This)         → anomaly_signals table → API → frontend Anomalies tab
                        WebSocket push on critical/high signals → NotificationCenter

Area 5 (Graph)        → Library DEPENDS_ON edges consumed by dependency risk model
                        Incident CAUSED_BY edges feed Poisson λ estimate
```

---

## Design Principles

**1. Never break the query path.**  
Every write from `agent/api.py` is fire-and-forget with `asyncio.ensure_future` and a bare `except: pass`. If Supabase is unavailable, the SSE stream is unaffected.

**2. No new Python dependencies.**  
Z-score uses `statistics.mean` / `statistics.stdev` (stdlib). Staleness and Poisson use `math.exp` (stdlib). No scikit-learn, no numpy.

**3. Deduplication at the signal level.**  
`insert_signal()` checks for an identical unresolved signal for the same (type, team, entity) in the last 2 hours before inserting. A 15-minute Celery task cannot flood the table.

**4. Team isolation everywhere.**  
Non-admin API callers are scoped to `user.get("team_id")` regardless of query params. Admin and org_admin can query across teams.

**5. Celery workers cannot push WebSockets directly.**  
Workers run in a separate OS process; `_notification_clients` in `src/ws/router.py` is empty there. Real-time push uses an in-process FastAPI `BackgroundTask` via `src/anomaly/notifier.py`, rate-limited to once per 5 minutes.
