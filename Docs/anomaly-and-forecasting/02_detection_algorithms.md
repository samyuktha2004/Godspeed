# 02 · Detection Algorithms

All four algorithms live in `src/anomaly/tasks.py`. No external ML libraries are used — only Python stdlib (`statistics`, `math`).

---

## Algorithm 1: Z-Score Query Spike / Drop Detection

**Celery task:** `poll_metrics_anomalies` — every 15 minutes (queue: `polling`)  
**Function:** `run_zscore_anomaly_detection()`  
**Signal types produced:** `query_spike`, `query_drop`

### How It Works

For every team with at least 24 hours of history in `query_events_hourly`:

1. Fetch hourly query counts for the last 14 days (`get_hourly_counts(team_id, days=14)`)
2. Exclude the current (partial) hour from the baseline — it is still accumulating
3. Compute baseline mean (μ) and standard deviation (σ) using `statistics.mean` / `statistics.stdev`
4. Compute Z-score for the most recent complete hour:

```
Z = (current_count − μ) / σ
```

5. Flag as **spike** if `Z > 3.0`, **drop** if `Z < −2.0`

### Why Z > 3.0?

A Z-score above 3.0 means the observation is more than 3 standard deviations above the mean. Under a normal distribution, this occurs by chance less than 0.3% of the time — so when it happens, it is almost always a real event: an incident, a deployment failure, or a sudden surge of new users.

The drop threshold is softer (`−2.0`) because a quiet hour is less urgent than a spike but still worth flagging — it may indicate the integration broke silently.

### Severity Mapping

| Z-score magnitude | Severity |
|---|---|
| \|Z\| ≥ 5.0 | `critical` |
| \|Z\| ≥ 4.0 | `high` |
| \|Z\| ≥ 3.5 | `medium` |
| \|Z\| ≥ 3.0 | `low` |

### Edge Cases Handled

| Condition | Handling |
|---|---|
| Fewer than 24 hourly rows | Skip team — insufficient baseline |
| `stdev == 0` (constant rate) | Skip team — Z-score undefined |
| `baseline < 2 rows` | Skip team — `statistics.stdev` requires ≥ 2 values |
| Duplicate signal within 2 hours | `insert_signal()` dedup suppresses it |

### Example

A team normally sends ~25 queries/hour (μ = 25, σ = 8). At 14:00, they send 72 queries:

```
Z = (72 − 25) / 8 = 5.875  →  severity: critical
```

The signal is inserted with `score = 5.875` and `details.hour_bucket = "2026-05-17T14:00:00"`.

---

## Algorithm 2: Escalation Rate Trend Detection

**Runs alongside:** Z-score task (same `poll_metrics_anomalies` Celery beat)  
**Function:** `_check_escalation_trend(team_id, rows, now)`  
**Signal type produced:** `escalation_trend`

### How It Works

Using the same hourly rows fetched for Z-score:

1. Split rows into two 7-day windows:
   - **Current window:** `now − 7d` to `now`
   - **Prior window:** `now − 14d` to `now − 7d`

2. For each window, sum `query_count` and `escalation_count`

3. Compute escalation rate per window:

```
escalation_rate = escalation_count / query_count
```

4. Compute ratio:

```
ratio = current_rate / prior_rate
```

5. If `ratio > 1.5` and `current_queries ≥ 10` (noise threshold), insert signal

### Why 10-Query Minimum?

A team with 2 total queries and 1 escalation has a 50% escalation rate. That is meaningless — one bad query doubles the rate. The 10-query floor ensures the rate is statistically grounded.

### Severity

| Ratio | Severity |
|---|---|
| ratio > 2.5 | `high` |
| ratio > 1.5 | `medium` |

### Example

- Prior 7 days: 60 queries, 6 escalations → rate = 10%
- Current 7 days: 52 queries, 10 escalations → rate = 19.2%
- Ratio: 1.92 → `medium` severity

The team's escalation rate is 92% worse than the prior week.

---

## Algorithm 3: Document Staleness Scoring

**Celery task:** `compute_staleness_scores` — daily at 03:00 UTC (queue: `low`)  
**Function:** `run_staleness_scoring()`  
**Signal type produced:** `staleness`

### The Core Formula

```
staleness_risk = age_factor × query_pressure
```

Both factors are independent, each in [0.0, 1.0]. Their product gives a score in [0.0, 1.0].

### Age Factor

Exponential decay with a 90-day half-life (actually ~62 days to 50%, ~90 days to 63%):

```
age_factor = 1 − exp(−age_days / 90)
```

| Document age | age_factor |
|---|---|
| 0 days (just updated) | 0.000 |
| 30 days | 0.283 |
| 60 days | 0.487 |
| 90 days | 0.632 |
| 180 days | 0.865 |
| 365 days | 0.983 |
| 2 years | 0.9998 |

The exponential shape reflects reality: most knowledge stales rapidly in the first 3 months, then slows. A 3-year-old document and a 2-year-old document are both "very stale."

### Query Pressure

How heavily queried is this document's team in the last 30 days, relative to all teams?

```
query_pressure = min(1.0, monthly_team_query_count / p95_team_query_count)
```

The p95 value is the 95th percentile of monthly query counts across all teams. This means only the top 5% most-active teams get `query_pressure = 1.0`. A moderately active team might get 0.4–0.6.

**Why team-level, not document-level?**  
The current `query_events` schema stores per-query agent metrics (chunk counts) but does not track *which document* each chunk came from. Team-level pressure is a conservative proxy — it correctly identifies high-risk documents in busy teams, and under-weights documents in quiet teams (which is the safe direction: a stale doc nobody queries is low priority).

### Severity

| `staleness_risk` | Severity |
|---|---|
| ≥ 0.8 | `critical` |
| ≥ 0.6 | `high` |
| ≥ 0.3 | `medium` |
| < 0.3 (but ≥ 0.1) | `low` |
| < 0.1 | Not inserted (below noise floor) |

### Example

A Kubernetes runbook last updated 8 months ago (240 days), in a team that sends 180 queries/month when p95 is 250:

```
age_factor     = 1 − exp(−240 / 90) = 0.931
query_pressure = min(1.0, 180 / 250) = 0.72
staleness_risk = 0.931 × 0.72       = 0.670  →  high
```

The same runbook in a team that sends 5 queries/month:

```
query_pressure = min(1.0, 5 / 250) = 0.02
staleness_risk = 0.931 × 0.02      = 0.019  →  below threshold, not inserted
```

### Cleanup

At the end of every staleness run, `purge_old_events()` deletes `query_events` rows older than 90 days, keeping the table bounded.

---

## Algorithm 4: Dependency Risk Modelling

**Celery task:** `compute_dependency_risk` — daily at 03:30 UTC (queue: `low`)  
**Function:** `run_dependency_risk_modeling()`  
**Signal type produced:** `dependency_risk`

### The Risk Formula

Three independent sub-scores, weighted and summed:

```
risk = 0.40 × version_lag
     + 0.35 × downstream_normalized
     + 0.25 × incident_rate
```

All three sub-scores are normalised to [0.0, 1.0]. The final risk score is also [0.0, 1.0].

### Sub-Score 1: Version Lag

Derived from semantic versioning distance between `lib.version` and `lib.latest_version` in Neo4j:

| Gap | Score |
|---|---|
| Different major version | 1.0 |
| Different minor version (same major) | 0.6 |
| Different patch (same major.minor) | 0.2 |
| Same version | 0.0 |

A library that is 2 major versions behind still scores 1.0 — version lag is binary once you're behind a major boundary.

### Sub-Score 2: Downstream Exposure

How many other services `DEPENDS_ON` this library in the Neo4j graph:

```
downstream_normalized = min(1.0, downstream_count / max_downstream_across_all_libs)
```

A library with 12 dependents when the most-connected library has 15 gets `downstream_normalized = 0.8`. This is an org-wide normalisation — the denominator is the most-exposed library in the entire graph.

### Sub-Score 3: Historical Incident Rate

How many `Incident` nodes have a `CAUSED_BY` edge to this library:

```
incident_rate = min(1.0, incident_count / 365)
```

This caps at 1.0 when there have been ≥ 365 incidents (one per day) — which is theoretical. In practice, even 5 incidents scores `incident_rate = 0.0137`, a meaningful non-zero signal.

### Poisson Forecast: Probability of Incident in Next 30 Days

The Poisson model treats historical incidents as a counting process with rate λ:

```
λ = incident_count / 365   (incidents per day)

P(at least one incident in next 30 days) = 1 − exp(−λ × 30)
```

This gives a concrete probability — not a vague "high risk" label — that can be shown in the UI:

| incident_count | λ | P(incident in 30d) |
|---|---|---|
| 0 | 0 | 0% |
| 1 | 0.00274 | 7.8% |
| 2 | 0.00548 | 15.3% |
| 5 | 0.01370 | 33.6% |
| 12 | 0.03288 | 63.0% |

### Neo4j Query

```cypher
MATCH (lib:Library)
OPTIONAL MATCH (lib)<-[:DEPENDS_ON]-(downstream)
OPTIONAL MATCH (lib)<-[:CAUSED_BY]-(inc:Incident)
RETURN lib.name                              AS name,
       coalesce(lib.version, '0.0.0')        AS current_version,
       coalesce(lib.latest_version, '0.0.0') AS latest_version,
       count(DISTINCT downstream)            AS downstream_count,
       count(DISTINCT inc)                   AS incident_count
```

This is the only query to Neo4j in the algorithm — all scoring is done in Python after fetching.

### Severity

| `risk` | Severity |
|---|---|
| ≥ 0.70 | `critical` |
| ≥ 0.50 | `high` |
| ≥ 0.30 | `medium` |
| < 0.30 | `low` |

### Example

`fastapi` library: 2 major versions behind, 8 downstream services, 2 incidents in Neo4j. Max downstream across all libs is 15.

```
version_lag           = 1.0      (major version gap)
downstream_normalized = 8/15 = 0.533
incident_rate         = 2/365 = 0.00548

risk = 0.40×1.0 + 0.35×0.533 + 0.25×0.00548
     = 0.400 + 0.187 + 0.001
     = 0.588  →  high

λ = 2/365 = 0.00548
poisson_30d = 1 − exp(−0.00548 × 30) = 15.3%
```

---

## Algorithm Interaction

The four algorithms are independent and run on separate schedules, but they complement each other:

```
A query spike on team_infra (Z=4.8, critical)
  ↓
Cross-reference gs:topics → "kubernetes" dominant this hour
  ↓
Staleness algorithm (ran last night) already flagged:
  "k8s-ingress-runbook.md" → staleness_risk=0.72 (high)
  ↓
Dependency risk algorithm (ran last night) flagged:
  "helm" library → risk=0.61 (high), poisson_30d=22%
  ↓
Three active anomaly_signals pointing at same root cause
→ Alert feed surfaces them together, sorted by severity
```

No automated correlation is built yet — the signals exist separately in `anomaly_signals`. Grouping them is a UI/UX concern (future Area 4 extension).
