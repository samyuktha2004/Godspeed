"""Supabase persistence layer for anomaly detection.

Every public function is wrapped in try/except so callers never crash
if Supabase is unavailable or misconfigured.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _sb():
    """Return the Supabase sync client (service role key, bypasses RLS)."""
    from src.auth.db import _client
    return _client()


# ── query_events ──────────────────────────────────────────────────────────────

def upsert_query_event(event: dict) -> None:
    """Write one query event row, idempotent on event_id."""
    try:
        _sb().table("query_events").upsert(
            {
                "event_id":        event["id"],
                "team_id":         event.get("team_id", "unknown"),
                "session_id":      event.get("session_id"),
                "success":         event.get("success", True),
                "duration_ms":     event.get("duration_ms"),
                "escalated":       event.get("escalated", False),
                "guardrail_score": event.get("guardrail_score"),
                "agent_metrics":   event.get("agents", {}),
                "created_at":      event.get("created_at", datetime.utcnow().isoformat()),
            },
            on_conflict="event_id",
            ignore_duplicates=True,
        ).execute()
    except Exception:
        logger.warning("anomaly_db: upsert_query_event failed", exc_info=True)


async def async_upsert_query_event(event: dict) -> None:
    """Async shim — runs the sync upsert in the default executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, upsert_query_event, event)


# ── query_events_hourly ───────────────────────────────────────────────────────

def aggregate_hourly(team_id: str, hour_bucket: str) -> None:
    """Recompute one (team_id, hour_bucket) row via the Supabase RPC."""
    try:
        _sb().rpc("aggregate_hourly_bucket", {
            "p_team_id": team_id,
            "p_hour":    hour_bucket,
        }).execute()
    except Exception:
        logger.warning(
            "anomaly_db: aggregate_hourly failed team=%s hour=%s",
            team_id, hour_bucket, exc_info=True,
        )


def get_hourly_counts(team_id: str, days: int = 14) -> list[dict]:
    """Return hourly aggregate rows for the last N days for a team."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        result = (
            _sb()
            .table("query_events_hourly")
            .select("hour_bucket,query_count,escalation_count")
            .eq("team_id", team_id)
            .gte("hour_bucket", cutoff)
            .order("hour_bucket", desc=False)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("anomaly_db: get_hourly_counts failed", exc_info=True)
        return []


def get_all_team_ids() -> list[str]:
    """Return distinct team_ids with events in the last 90 days."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
        result = (
            _sb()
            .table("query_events")
            .select("team_id")
            .gte("created_at", cutoff)
            .execute()
        )
        return list({r["team_id"] for r in (result.data or [])})
    except Exception:
        logger.warning("anomaly_db: get_all_team_ids failed", exc_info=True)
        return []


# ── anomaly_signals ───────────────────────────────────────────────────────────

def insert_signal(
    signal_type: str,
    severity: str,
    score: float,
    details: dict,
    team_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict | None:
    """Insert one anomaly signal with 2-hour dedup suppression.

    If an identical unresolved signal already exists for the same
    (signal_type, team_id, entity_id) within the last 2 hours, the
    insert is skipped and None is returned.
    """
    try:
        two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        dupe_q = (
            _sb()
            .table("anomaly_signals")
            .select("id")
            .eq("signal_type", signal_type)
            .eq("resolved", False)
            .gte("detected_at", two_hours_ago)
        )
        if team_id:
            dupe_q = dupe_q.eq("team_id", team_id)
        if entity_id:
            dupe_q = dupe_q.eq("entity_id", entity_id)
        if dupe_q.execute().data:
            return None  # suppress duplicate

        row: dict = {
            "signal_type": signal_type,
            "severity":    severity,
            "score":       score,
            "details":     details,
        }
        if team_id:     row["team_id"]     = team_id
        if entity_type: row["entity_type"] = entity_type
        if entity_id:   row["entity_id"]   = entity_id

        result = _sb().table("anomaly_signals").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception:
        logger.warning("anomaly_db: insert_signal failed type=%s", signal_type, exc_info=True)
        return None


def get_signals(
    team_id: str | None,
    severity: str | None,
    signal_type: str | None,
    resolved: bool,
    limit: int,
) -> list[dict]:
    try:
        q = (
            _sb()
            .table("anomaly_signals")
            .select("*")
            .eq("resolved", resolved)
            .order("detected_at", desc=True)
            .limit(limit)
        )
        if team_id:     q = q.eq("team_id", team_id)
        if severity:    q = q.eq("severity", severity)
        if signal_type: q = q.eq("signal_type", signal_type)
        return q.execute().data or []
    except Exception:
        logger.warning("anomaly_db: get_signals failed", exc_info=True)
        return []


def resolve_signal(signal_id: str, resolver_user_id: str) -> bool:
    try:
        _sb().table("anomaly_signals").update({
            "resolved":    True,
            "resolved_by": resolver_user_id,
            "resolved_at": datetime.utcnow().isoformat(),
        }).eq("id", signal_id).eq("resolved", False).execute()
        return True
    except Exception:
        logger.warning("anomaly_db: resolve_signal failed id=%s", signal_id, exc_info=True)
        return False


def get_signals_summary() -> dict:
    """Return unresolved signal counts grouped by type and severity."""
    try:
        result = (
            _sb()
            .table("anomaly_signals")
            .select("signal_type,severity")
            .eq("resolved", False)
            .execute()
        )
        rows = result.data or []
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in rows:
            by_type[r["signal_type"]] = by_type.get(r["signal_type"], 0) + 1
            by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1
        return {"total": len(rows), "by_type": by_type, "by_severity": by_severity}
    except Exception:
        logger.warning("anomaly_db: get_signals_summary failed", exc_info=True)
        return {"total": 0, "by_type": {}, "by_severity": {}}


def get_staleness_top(limit: int = 30) -> list[dict]:
    try:
        result = (
            _sb()
            .table("anomaly_signals")
            .select("entity_id,score,details,detected_at")
            .eq("signal_type", "staleness")
            .eq("resolved", False)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("anomaly_db: get_staleness_top failed", exc_info=True)
        return []


def get_dependency_risk(limit: int = 50) -> list[dict]:
    try:
        result = (
            _sb()
            .table("anomaly_signals")
            .select("entity_id,score,details,detected_at")
            .eq("signal_type", "dependency_risk")
            .eq("resolved", False)
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("anomaly_db: get_dependency_risk failed", exc_info=True)
        return []


def purge_old_events() -> int:
    """Delete query_events older than 90 days. Returns approximate deleted count."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
        result = _sb().table("query_events").delete().lt("created_at", cutoff).execute()
        deleted = len(result.data or [])
        if deleted:
            logger.info("anomaly_db: purged %d old query_events", deleted)
        return deleted
    except Exception:
        logger.warning("anomaly_db: purge_old_events failed", exc_info=True)
        return 0
