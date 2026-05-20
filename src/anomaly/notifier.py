"""In-process WebSocket broadcast bridge for anomaly signals.

Celery workers run in a separate OS process, so `_notification_clients`
in src/ws/router.py is always empty there. Real-time push is handled here:
a FastAPI BackgroundTask (running inside the API server process) polls for
recently-detected critical/high signals and calls broadcast_notification().

Rate-limited to one check per 5 minutes via a module-level timestamp.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_last_notified: datetime = datetime.utcnow() - timedelta(minutes=5)


async def broadcast_new_critical_signals() -> None:
    """Check for new critical/high anomaly signals and push via WebSocket.

    Called as a BackgroundTask from GET /api/anomaly/signals.
    No-ops if fewer than 5 minutes have elapsed since the last dispatch.
    """
    global _last_notified
    now = datetime.utcnow()

    if (now - _last_notified).total_seconds() < 300:
        return

    _last_notified = now

    try:
        from src.anomaly.db import get_signals
        from src.ws.router import broadcast_notification

        recent_signals = get_signals(
            team_id=None,
            severity=None,
            signal_type=None,
            resolved=False,
            limit=20,
        )

        ten_minutes_ago = now - timedelta(minutes=10)
        for sig in recent_signals:
            if sig.get("severity") not in ("critical", "high"):
                continue
            try:
                detected = datetime.fromisoformat(
                    str(sig["detected_at"]).replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                continue
            if detected < ten_minutes_ago:
                continue

            ws_type = (
                "escalation_spike"
                if sig["signal_type"] in ("query_spike", "query_drop", "escalation_trend")
                else "knowledge_gap"
            )
            entity_suffix = f" — {sig['entity_id']}" if sig.get("entity_id") else ""
            await broadcast_notification({
                "type":      ws_type,
                "message":   sig["signal_type"].replace("_", " ").title() + entity_suffix,
                "severity":  sig["severity"],
                "timestamp": sig["detected_at"],
            })

    except Exception:
        logger.warning("notifier: broadcast_new_critical_signals failed", exc_info=True)
