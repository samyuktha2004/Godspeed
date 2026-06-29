"""Anomaly detection API — /api/anomaly endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from src.auth.deps import get_current_user, require_role
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])


@router.get("/signals")
async def list_signals(
    background_tasks: BackgroundTasks,
    team_id:     str | None = Query(default=None),
    severity:    str | None = Query(default=None),
    signal_type: str | None = Query(default=None, alias="type"),
    resolved:    bool       = Query(default=False),
    limit:       int        = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
) -> dict:
    # Non-admin users are scoped to their own team only
    effective_team = team_id
    if user.get("role") != "admin":
        effective_team = user.get("team_id")

    from src.anomaly.db import get_signals
    signals = get_signals(
        team_id=effective_team,
        severity=severity,
        signal_type=signal_type,
        resolved=resolved,
        limit=limit,
    )

    # Dispatch WebSocket push for new critical/high signals (in-process, rate-limited)
    from src.anomaly.notifier import broadcast_new_critical_signals
    background_tasks.add_task(broadcast_new_critical_signals)

    return {"signals": signals, "total": len(signals)}


@router.get("/signals/summary")
async def signals_summary(
    user: dict = Depends(get_current_user),
) -> dict:
    from src.anomaly.db import get_signals_summary
    team_id = None if user.get("role") == "admin" else user.get("team_id")
    return get_signals_summary(team_id=team_id)


@router.patch("/signals/{signal_id}/resolve")
async def resolve_signal(
    signal_id: str,
    user: dict = Depends(require_role("admin", "manager")),
) -> dict:
    from src.anomaly.db import get_signal_by_id, resolve_signal as _resolve
    if user.get("role") == "manager":
        signal = get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found or already resolved")
        if signal.get("team_id") != user.get("team_id"):
            raise HTTPException(status_code=403, detail="Cannot resolve signals outside your team")
    ok = _resolve(signal_id, resolver_user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Signal not found or already resolved")
    return {"ok": True}


@router.get("/query-patterns")
async def query_patterns(
    team_id: str | None = Query(default=None),
    days:    int        = Query(default=14, ge=1, le=90),
    user: dict = Depends(get_current_user),
) -> dict:
    """Hourly query counts with anomaly overlay markers for QuerySpikeChart."""
    from src.anomaly.db import get_hourly_counts, get_signals

    effective_team = team_id
    if user.get("role") != "admin":
        effective_team = user.get("team_id") or team_id

    if not effective_team:
        return {"hourly": [], "team_id": None}

    hourly  = get_hourly_counts(effective_team, days=days)
    signals = get_signals(
        team_id=effective_team,
        severity=None,
        signal_type=None,
        resolved=False,
        limit=200,
    )

    # Build a lookup of anomaly info keyed by "YYYY-MM-DDTHH" prefix
    anomaly_map: dict[str, dict] = {}
    for sig in signals:
        if sig["signal_type"] in ("query_spike", "query_drop"):
            hb = (sig.get("details") or {}).get("hour_bucket", "")
            if hb:
                anomaly_map[hb[:13]] = {
                    "score":    sig["score"],
                    "type":     sig["signal_type"],
                    "severity": sig["severity"],
                }

    result = []
    for row in hourly:
        hb_str  = str(row["hour_bucket"])
        anomaly = anomaly_map.get(hb_str[:13])
        result.append({
            "hour":             hb_str,
            "count":            row["query_count"],
            "escalations":      row["escalation_count"],
            "anomaly_score":    anomaly["score"]    if anomaly else None,
            "anomaly_type":     anomaly["type"]     if anomaly else None,
            "anomaly_severity": anomaly["severity"] if anomaly else None,
        })

    return {"hourly": result, "team_id": effective_team}


@router.get("/staleness")
async def staleness_list(
    limit: int = Query(default=30, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    from src.anomaly.db import get_staleness_top
    team_id = None if user.get("role") == "admin" else user.get("team_id")
    items = get_staleness_top(limit=limit, team_id=team_id)
    return {"documents": items, "total": len(items)}


@router.get("/dependency-risk")
async def dependency_risk(
    user: dict = Depends(get_current_user),
) -> dict:
    from src.anomaly.db import get_dependency_risk
    team_id = None if user.get("role") == "admin" else user.get("team_id")
    items = get_dependency_risk(team_id=team_id)
    return {"libraries": items, "total": len(items)}
