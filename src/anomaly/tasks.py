"""Anomaly detection algorithms — called from Celery tasks in src/celery_app.py.

Three top-level functions are exported:
  run_zscore_anomaly_detection()   — query spikes + escalation trend (every 15 min)
  run_staleness_scoring()          — document staleness risk (daily 03:00 UTC)
  run_dependency_risk_modeling()   — library risk + Poisson forecast (daily 03:30 UTC)

All use only stdlib (statistics, math) — no new pip dependencies.
"""

from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Z-score helpers ───────────────────────────────────────────────────────────

def _zscore_severity(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= 5.0:
        return "critical"
    if abs_z >= 4.0:
        return "high"
    if abs_z >= 3.5:
        return "medium"
    return "low"


# ── 1. Z-score spike detection + escalation trend ────────────────────────────

def run_zscore_anomaly_detection() -> None:
    """For every active team: compute hourly Z-scores and escalation rate trends.

    Reads from query_events_hourly (pre-aggregated).
    Writes to anomaly_signals via insert_signal() with 2-hour dedup suppression.
    Fires WebSocket broadcast for critical/high signals (best-effort).
    """
    from src.anomaly.db import get_all_team_ids, get_hourly_counts, insert_signal

    team_ids = get_all_team_ids()
    now = datetime.utcnow()
    current_hour = now.replace(minute=0, second=0, microsecond=0).isoformat()

    for team_id in team_ids:
        try:
            rows = get_hourly_counts(team_id, days=14)
            if len(rows) < 24:
                continue

            counts = [r["query_count"] for r in rows]
            # Exclude the current (partial) hour from the baseline
            baseline = counts[:-1]

            if len(baseline) < 2:
                continue

            mean  = statistics.mean(baseline)
            stdev = statistics.stdev(baseline)

            if stdev == 0:
                continue

            current_count = counts[-1]
            z = (current_count - mean) / stdev

            if z > 3.0:
                signal = insert_signal(
                    signal_type="query_spike",
                    team_id=team_id,
                    entity_type="Team",
                    entity_id=team_id,
                    severity=_zscore_severity(z),
                    score=round(z, 3),
                    details={
                        "z_score":         round(z, 3),
                        "current_count":   current_count,
                        "baseline_mean":   round(mean, 2),
                        "baseline_stdev":  round(stdev, 2),
                        "hour_bucket":     current_hour,
                        "window_hours":    len(baseline),
                    },
                )
                if signal and signal.get("severity") in ("critical", "high"):
                    _try_broadcast({
                        "type":      "escalation_spike",
                        "message":   f"Query spike for team {team_id}: Z={z:.1f}",
                        "timestamp": now.isoformat(),
                    })

            elif z < -2.0:
                insert_signal(
                    signal_type="query_drop",
                    team_id=team_id,
                    entity_type="Team",
                    entity_id=team_id,
                    severity=_zscore_severity(z),
                    score=round(z, 3),
                    details={
                        "z_score":        round(z, 3),
                        "current_count":  current_count,
                        "baseline_mean":  round(mean, 2),
                        "hour_bucket":    current_hour,
                    },
                )

            _check_escalation_trend(team_id, rows, now)

        except Exception:
            logger.warning("zscore: error for team %s", team_id, exc_info=True)


def _check_escalation_trend(team_id: str, rows: list[dict], now: datetime) -> None:
    from src.anomaly.db import insert_signal

    cutoff_7d  = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)

    current_window: list[dict] = []
    prior_window:   list[dict] = []

    for r in rows:
        try:
            hb = datetime.fromisoformat(
                str(r["hour_bucket"]).replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except Exception:
            continue
        if hb >= cutoff_7d:
            current_window.append(r)
        elif hb >= cutoff_14d:
            prior_window.append(r)

    current_queries     = sum(r["query_count"]     for r in current_window)
    current_escalations = sum(r["escalation_count"] for r in current_window)
    prior_queries       = sum(r["query_count"]     for r in prior_window)
    prior_escalations   = sum(r["escalation_count"] for r in prior_window)

    if current_queries < 10:
        return

    current_rate = current_escalations / current_queries if current_queries else 0.0
    prior_rate   = prior_escalations   / prior_queries   if prior_queries   else 0.0

    if prior_rate == 0.0:
        return

    ratio = current_rate / prior_rate
    if ratio > 1.5:
        severity = "high" if ratio > 2.5 else "medium"
        insert_signal(
            signal_type="escalation_trend",
            team_id=team_id,
            entity_type="Team",
            entity_id=team_id,
            severity=severity,
            score=round(ratio, 3),
            details={
                "ratio":                  round(ratio, 3),
                "current_rate":           round(current_rate, 4),
                "prior_rate":             round(prior_rate,   4),
                "current_total_queries":  current_queries,
                "prior_total_queries":    prior_queries,
            },
        )


# ── 2. Staleness scoring ──────────────────────────────────────────────────────

def run_staleness_scoring() -> None:
    """Compute staleness_risk = age_factor × query_pressure for all documents.

    age_factor    = 1 − exp(−age_days / 90)   (exponential decay, half-life ~62 days)
    query_pressure = min(1.0, monthly_team_queries / p95_monthly_team_queries)

    Documents with staleness_risk < 0.1 are skipped to avoid noise.
    Cleans up query_events older than 90 days at the end of each run.
    """
    from src.anomaly.db import insert_signal, purge_old_events
    from src.auth.db import _client as _sb_client

    sb  = _sb_client()
    now = datetime.utcnow()

    # Load all documents
    try:
        docs = sb.table("documents").select("id,doc_id,title,team_id,updated_at").execute().data or []
    except Exception:
        logger.warning("staleness: failed to load documents", exc_info=True)
        return

    if not docs:
        return

    # Monthly query count per team (proxy for query pressure at team level)
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    team_query_counts: dict[str, int] = {}
    try:
        rows = (
            sb.table("query_events")
            .select("team_id")
            .gte("created_at", cutoff_30d)
            .execute()
            .data or []
        )
        for r in rows:
            tid = r.get("team_id", "unknown")
            team_query_counts[tid] = team_query_counts.get(tid, 0) + 1
    except Exception:
        logger.warning("staleness: team query count failed", exc_info=True)

    # p95 of team query counts
    count_values = sorted(team_query_counts.values()) or [1]
    p95_idx   = max(0, int(len(count_values) * 0.95) - 1)
    p95_count = count_values[p95_idx] or 1

    for doc in docs:
        try:
            try:
                updated = datetime.fromisoformat(
                    str(doc["updated_at"]).replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                updated = now - timedelta(days=180)

            age_days       = max(0, (now - updated).days)
            age_factor     = 1.0 - math.exp(-age_days / 90.0)
            monthly_count  = team_query_counts.get(doc.get("team_id", ""), 0)
            query_pressure = min(1.0, monthly_count / p95_count)
            staleness_risk = round(age_factor * query_pressure, 4)

            if staleness_risk < 0.1:
                continue

            severity = (
                "critical" if staleness_risk >= 0.8 else
                "high"     if staleness_risk >= 0.6 else
                "medium"   if staleness_risk >= 0.3 else
                "low"
            )

            insert_signal(
                signal_type="staleness",
                team_id=doc.get("team_id"),
                entity_type="Document",
                entity_id=doc.get("doc_id"),
                severity=severity,
                score=staleness_risk,
                details={
                    "title":          doc.get("title", ""),
                    "age_days":       age_days,
                    "age_factor":     round(age_factor,     4),
                    "query_pressure": round(query_pressure, 4),
                    "updated_at":     doc.get("updated_at"),
                },
            )
        except Exception:
            logger.warning("staleness: error on doc %s", doc.get("doc_id"), exc_info=True)

    purge_old_events()


# ── 3. Dependency risk modelling ──────────────────────────────────────────────

def run_dependency_risk_modeling() -> None:
    """Score every Library node in Neo4j for dependency risk.

    risk = 0.40 × version_lag  +  0.35 × downstream_normalized  +  0.25 × incident_rate
    poisson_30d = 1 − exp(−(incident_count / 365) × 30)
    """
    from src.anomaly.db import insert_signal

    rows = _fetch_library_risk_rows()
    if not rows:
        logger.info("dep_risk: no library rows from Neo4j")
        return

    max_downstream = max((r.get("downstream_count", 0) for r in rows), default=1) or 1

    for r in rows:
        try:
            name           = r.get("name", "")
            current_ver    = r.get("current_version",  "0.0.0")
            latest_ver     = r.get("latest_version",   "0.0.0")
            downstream     = int(r.get("downstream_count", 0))
            incident_count = int(r.get("incident_count",  0))

            version_lag           = _version_lag_score(current_ver, latest_ver)
            downstream_normalized = min(1.0, downstream / max_downstream)
            incident_rate         = min(1.0, incident_count / 365.0)

            risk = round(
                0.40 * version_lag +
                0.35 * downstream_normalized +
                0.25 * incident_rate,
                4,
            )

            lam          = incident_count / 365.0
            poisson_30d  = round(1.0 - math.exp(-lam * 30), 4)

            severity = (
                "critical" if risk >= 0.7 else
                "high"     if risk >= 0.5 else
                "medium"   if risk >= 0.3 else
                "low"
            )

            insert_signal(
                signal_type="dependency_risk",
                team_id=None,
                entity_type="Library",
                entity_id=name,
                severity=severity,
                score=risk,
                details={
                    "library_name":           name,
                    "current_version":        current_ver,
                    "latest_version":         latest_ver,
                    "version_lag":            round(version_lag,           4),
                    "downstream_count":       downstream,
                    "downstream_normalized":  round(downstream_normalized, 4),
                    "incident_count":         incident_count,
                    "incident_rate":          round(incident_rate,         4),
                    "poisson_30d":            poisson_30d,
                },
            )
        except Exception:
            logger.warning("dep_risk: error on library %s", r.get("name"), exc_info=True)


def _fetch_library_risk_rows() -> list[dict]:
    import asyncio

    async def _query() -> list[dict]:
        from graph_store.config import settings as neo4j_cfg
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            neo4j_cfg.neo4j_uri,
            auth=(neo4j_cfg.neo4j_username, neo4j_cfg.neo4j_password),
        )
        try:
            async with driver.session() as session:
                result = await session.run("""
                    MATCH (lib:Library)
                    OPTIONAL MATCH (lib)<-[:DEPENDS_ON]-(downstream)
                    OPTIONAL MATCH (lib)<-[:CAUSED_BY]-(inc:Incident)
                    RETURN lib.name                              AS name,
                           coalesce(lib.version, '0.0.0')        AS current_version,
                           coalesce(lib.latest_version, '0.0.0') AS latest_version,
                           count(DISTINCT downstream)            AS downstream_count,
                           count(DISTINCT inc)                   AS incident_count
                """)
                return await result.data()
        finally:
            await driver.close()

    try:
        return asyncio.run(_query())
    except Exception:
        logger.warning("dep_risk: neo4j fetch failed", exc_info=True)
        return []


def _version_lag_score(current: str, latest: str) -> float:
    """Return 0.0–1.0 based on semver distance. Falls back to 0.5 on parse error."""
    try:
        def _parts(v: str) -> tuple[int, int, int]:
            parts = v.lstrip("v").split(".")[:3]
            ints = [(int(p) if p.isdigit() else 0) for p in (parts + ["0", "0", "0"])[:3]]
            return ints[0], ints[1], ints[2]

        c = _parts(current)
        l = _parts(latest)
        if l[0] > c[0]:
            return 1.0   # major version behind
        if l[1] > c[1]:
            return 0.6   # minor version behind
        if l[2] > c[2]:
            return 0.2   # patch behind
        return 0.0
    except Exception:
        return 0.5


# ── WebSocket broadcast (best-effort, in-process only) ───────────────────────

def _try_broadcast(payload: dict) -> None:
    """Best-effort WebSocket push from a Celery worker.

    Celery workers run in a separate process so _notification_clients in
    src/ws/router.py will be empty here. This is intentional — real-time
    push is handled by src/anomaly/notifier.py (in-process BackgroundTask).
    This call is a no-op in the worker context but kept for testability.
    """
    try:
        import asyncio
        from src.ws.router import broadcast_notification
        asyncio.run(broadcast_notification(payload))
    except Exception:
        pass
