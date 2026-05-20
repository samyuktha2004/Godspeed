# 03 · API Reference — `/api/anomaly`

**Router file:** `src/anomaly/router.py`  
**Registered in:** `main.py`  
**Auth:** All endpoints require a valid session cookie (`get_current_user`). Team isolation is enforced server-side for non-admin roles.

---

## `GET /api/anomaly/signals`

List anomaly signals with optional filters. Non-admin users are automatically scoped to their own `team_id`.

### Query Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `type` | string | — | Filter by `signal_type` (`query_spike`, `query_drop`, `escalation_trend`, `staleness`, `dependency_risk`) |
| `severity` | string | — | Filter by `severity` (`critical`, `high`, `medium`, `low`) |
| `team_id` | string | — | Admin/org_admin only — query a specific team. Non-admins are always scoped to their own team. |
| `resolved` | boolean | `false` | Include resolved signals |
| `limit` | integer | `50` | Max rows returned (1–200) |

### Response

```json
{
  "signals": [
    {
      "id": "3f2a1b4c-...",
      "team_id": "team_infra",
      "signal_type": "query_spike",
      "entity_type": "Team",
      "entity_id": "team_infra",
      "severity": "critical",
      "score": 5.875,
      "details": {
        "z_score": 5.875,
        "current_count": 72,
        "baseline_mean": 25.4,
        "baseline_stdev": 7.9,
        "hour_bucket": "2026-05-17T14:00:00",
        "window_hours": 335
      },
      "resolved": false,
      "resolved_by": null,
      "resolved_at": null,
      "detected_at": "2026-05-17T14:15:03.221Z"
    }
  ],
  "total": 1
}
```

### Side Effect

Triggers `broadcast_new_critical_signals()` as a FastAPI `BackgroundTask`. Rate-limited to once per 5 minutes — pushes `escalation_spike` or `knowledge_gap` WebSocket notifications to connected clients for new critical/high signals detected in the last 10 minutes.

---

## `GET /api/anomaly/signals/summary`

Returns unresolved signal counts grouped by type and severity. Used by the frontend to render the severity badge strip at the top of the Anomalies tab.

### Response

```json
{
  "total": 7,
  "by_type": {
    "query_spike": 2,
    "staleness": 3,
    "dependency_risk": 2
  },
  "by_severity": {
    "critical": 1,
    "high": 3,
    "medium": 2,
    "low": 1
  }
}
```

---

## `PATCH /api/anomaly/signals/{signal_id}/resolve`

Mark a signal as resolved. **Admin / org_admin only** — returns `403` for other roles.

### Path Parameter

| Param | Description |
|---|---|
| `signal_id` | UUID of the `anomaly_signals` row |

### Response

```json
{ "ok": true }
```

Returns `404` if the signal does not exist or is already resolved.

**Effect:** Sets `resolved = true`, `resolved_by = user.id`, `resolved_at = now()` on the row. The signal is excluded from all `resolved=false` queries going forward.

---

## `GET /api/anomaly/query-patterns`

Returns hourly query counts for the last N days, with anomaly overlay markers. Powers `QuerySpikeChart.tsx`.

### Query Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `team_id` | string | — | Admin only. Non-admins use their session team. |
| `days` | integer | `14` | Lookback window (1–90) |

### Response

```json
{
  "team_id": "team_infra",
  "hourly": [
    {
      "hour": "2026-05-03T09:00:00+00:00",
      "count": 18,
      "escalations": 2,
      "anomaly_score": null,
      "anomaly_type": null,
      "anomaly_severity": null
    },
    {
      "hour": "2026-05-17T14:00:00+00:00",
      "count": 72,
      "escalations": 4,
      "anomaly_score": 5.875,
      "anomaly_type": "query_spike",
      "anomaly_severity": "critical"
    }
  ]
}
```

`anomaly_score`, `anomaly_type`, `anomaly_severity` are `null` for normal hours and populated for hours that have a matching unresolved `query_spike` or `query_drop` signal. The frontend uses these to render `ReferenceArea` overlays on the chart.

---

## `GET /api/anomaly/staleness`

Top documents by staleness risk score. Powers `StalenessRiskList.tsx`.

### Query Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | `30` | Max rows (1–100) |

### Response

```json
{
  "documents": [
    {
      "entity_id": "confluence:12345",
      "score": 0.671,
      "details": {
        "title": "Kubernetes Ingress Setup Guide",
        "age_days": 240,
        "age_factor": 0.931,
        "query_pressure": 0.72,
        "updated_at": "2025-09-20T10:00:00"
      },
      "detected_at": "2026-05-17T03:04:22.100Z"
    }
  ],
  "total": 1
}
```

Results are sorted descending by `score`. The `details` object contains all the inputs to the staleness formula, making it possible to explain the score in a tooltip.

---

## `GET /api/anomaly/dependency-risk`

Libraries scored by dependency risk, including Poisson incident probability. Powers the risk column added to `DependencyTracker.tsx`.

### Response

```json
{
  "libraries": [
    {
      "entity_id": "fastapi",
      "score": 0.588,
      "details": {
        "library_name": "fastapi",
        "current_version": "0.95.0",
        "latest_version": "0.115.0",
        "version_lag": 1.0,
        "downstream_count": 8,
        "downstream_normalized": 0.533,
        "incident_count": 2,
        "incident_rate": 0.0055,
        "poisson_30d": 0.153
      },
      "detected_at": "2026-05-17T03:34:11.200Z"
    }
  ],
  "total": 1
}
```

`poisson_30d` is the probability (0.0–1.0) that this library causes at least one incident in the next 30 days, modelled as a Poisson process on historical `CAUSED_BY` edges in Neo4j. Rendered in the UI as a percentage (e.g. "15% in 30d").

---

## Error Responses

All endpoints return standard HTTP error codes:

| Code | Cause |
|---|---|
| `401` | No valid session cookie |
| `403` | Insufficient role (e.g. non-admin calling PATCH /resolve) |
| `404` | Signal not found or already resolved |
| `500` | Unexpected internal error (Supabase/Neo4j unavailable) |

All 5xx errors are logged via `src/utils/logger.py` with request ID for tracing.

---

## Authentication Notes

The `/api/anomaly/signals` endpoint accepts an optional `team_id` query param:

- **admin / org_admin roles:** `team_id` param is respected — they can query any team's signals
- **All other roles:** `team_id` is overridden with `user.get("team_id")` from the session — the client cannot change this

The `dependency_risk` signals have `team_id = null` (library risk is org-wide). They appear for all roles regardless of team scoping.
