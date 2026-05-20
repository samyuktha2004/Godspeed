# 04 · Celery Jobs & Scheduling

---

## Overview

Three Celery tasks handle all anomaly detection. They run in the background, writing to `anomaly_signals` in Supabase. The FastAPI app only reads from that table — no detection logic runs in the request path.

```
Every 15 minutes   poll_metrics_anomalies    → Z-score + escalation trend
Daily 03:00 UTC    compute_staleness_scores  → Staleness risk for all documents
Daily 03:30 UTC    compute_dependency_risk   → Library risk from Neo4j
```

---

## Task Definitions

All tasks are defined in `src/celery_app.py`.

### `poll_metrics_anomalies`

```python
@shared_task(queue="polling", bind=True, max_retries=3)
def poll_metrics_anomalies(self):
    from src.anomaly.tasks import run_zscore_anomaly_detection
    run_zscore_anomaly_detection()
```

| Property | Value |
|---|---|
| Queue | `polling` (priority 3) |
| Schedule | Every `settings.sync.metrics_poll_interval` seconds (default 900s / 15 min) |
| Max retries | 3, with 120s countdown on failure |
| Runs | `run_zscore_anomaly_detection()` → `_check_escalation_trend()` |
| Writes | `query_spike`, `query_drop`, `escalation_trend` signals |

The interval is controlled by the `SYNC__METRICS_POLL_INTERVAL` env var (default 900). Lower it in staging to test faster:

```env
SYNC__METRICS_POLL_INTERVAL=60
```

### `compute_staleness_scores`

```python
@shared_task(queue="low", bind=True, max_retries=2)
def compute_staleness_scores(self):
    from src.anomaly.tasks import run_staleness_scoring
    run_staleness_scoring()
```

| Property | Value |
|---|---|
| Queue | `low` (priority 1) |
| Schedule | Daily at 03:00 UTC (`crontab(hour=3, minute=0)`) |
| Max retries | 2, with 300s countdown |
| Reads | `documents` table (Supabase), `query_events` table (Supabase) |
| Writes | `staleness` signals, purges `query_events` > 90 days |

### `compute_dependency_risk`

```python
@shared_task(queue="low", bind=True, max_retries=2)
def compute_dependency_risk(self):
    from src.anomaly.tasks import run_dependency_risk_modeling
    run_dependency_risk_modeling()
```

| Property | Value |
|---|---|
| Queue | `low` (priority 1) |
| Schedule | Daily at 03:30 UTC (`crontab(hour=3, minute=30)`) |
| Max retries | 2, with 300s countdown |
| Reads | Neo4j — `Library`, `DEPENDS_ON`, `CAUSED_BY` edges |
| Writes | `dependency_risk` signals |

---

## Beat Schedule Registration

Beat entries are registered in `setup_periodic_tasks()` in `src/celery_app.py`:

```python
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # ... existing tasks ...

    from celery.schedules import crontab

    sender.add_periodic_task(
        crontab(hour=3, minute=0),
        compute_staleness_scores.s(),
        name="compute-staleness-scores",
    )
    sender.add_periodic_task(
        crontab(hour=3, minute=30),
        compute_dependency_risk.s(),
        name="compute-dependency-risk",
    )
```

The `crontab` import is inside the function to avoid a module-level circular import with `celery.schedules`. This mirrors the pattern already used in `ingestion/jobs/celery_app.py`.

---

## Running Workers

Start a worker that handles the `polling` and `low` queues (required for anomaly tasks):

```bash
celery -A src.celery_app worker -Q polling,low --loglevel=info
```

Start the Beat scheduler:

```bash
celery -A src.celery_app beat --loglevel=info
```

For local development, combine both in one process:

```bash
celery -A src.celery_app worker --beat -Q polling,low,default --loglevel=info
```

---

## Manually Triggering Tasks

Useful for testing without waiting for the schedule:

```bash
# Trigger Z-score detection immediately
celery -A src.celery_app call src.celery_app.poll_metrics_anomalies

# Trigger staleness scoring
celery -A src.celery_app call src.celery_app.compute_staleness_scores

# Trigger dependency risk
celery -A src.celery_app call src.celery_app.compute_dependency_risk
```

Or from a Python shell:

```python
from src.celery_app import poll_metrics_anomalies, compute_staleness_scores
poll_metrics_anomalies.delay()
compute_staleness_scores.delay()
```

---

## Monitoring Task Execution

Check the `anomaly_signals` table after a run:

```sql
SELECT signal_type, severity, score, entity_id, detected_at
FROM   anomaly_signals
WHERE  detected_at > NOW() - INTERVAL '1 hour'
ORDER  BY detected_at DESC;
```

Check for failures in the Celery dead letter queue (`ingest:deadletter` Redis key) or via Flower:

```bash
pip install flower
celery -A src.celery_app flower --port=5555
# Open http://localhost:5555
```

---

## Failure Modes

| Task | Failure Mode | Effect |
|---|---|---|
| `poll_metrics_anomalies` | Supabase unavailable | `get_all_team_ids()` returns `[]` → task is a no-op, retried in 2 min |
| `poll_metrics_anomalies` | Fewer than 24h of data | All teams skipped — not enough baseline, no false alarms |
| `compute_staleness_scores` | `documents` table empty | Early return, no signals written |
| `compute_staleness_scores` | `query_events` table empty | All teams get `query_pressure = 0` → staleness_risk = 0 → no signals |
| `compute_dependency_risk` | Neo4j unavailable | `_fetch_library_risk_rows()` returns `[]` → early return |
| Any task | Unhandled exception | Celery retries up to max_retries, then marks task as FAILED |

All per-entity errors inside loops are caught individually (`except: logger.warning(...)`) — a single bad document or library never aborts the entire run.

---

## Adding a New Detection Algorithm

1. Add the algorithm function to `src/anomaly/tasks.py`
2. Add a new `@shared_task` to `src/celery_app.py`
3. Register with `sender.add_periodic_task(...)` in `setup_periodic_tasks()`
4. Use `insert_signal()` from `src/anomaly/db.py` with an appropriate `signal_type` value
5. Add a new `GET /api/anomaly/<endpoint>` if the frontend needs to query the results separately

The `signal_type` field in `anomaly_signals` is free-form text — no migration needed for a new type. Add it to the `signal_type` documentation in `01_data_layer.md`.
