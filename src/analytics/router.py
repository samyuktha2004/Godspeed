"""Analytics API — aggregates from Redis query events and Neo4j graph data."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Literal

import redis.asyncio as aioredis
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

DateRange = Literal["7d", "30d", "90d", "all"]

REDIS_QUERY_KEY = "gs:queries"  # lpush list; each item is a JSON query event


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _cutoff(date_range: DateRange) -> datetime | None:
    if date_range == "all":
        return None
    days = {"7d": 7, "30d": 30, "90d": 90}[date_range]
    return datetime.utcnow() - timedelta(days=days)


async def _load_events(date_range: DateRange) -> list[dict]:
    """Return query events from Redis. Returns [] if Redis is unavailable."""
    r = await _redis()
    try:
        raw_list = await r.lrange(REDIS_QUERY_KEY, 0, 9999)
    except Exception as exc:
        logger.warning("analytics_redis_read_failed", extra={"error": str(exc)})
        return []
    finally:
        await r.aclose()

    cutoff = _cutoff(date_range)
    events = []
    for raw in raw_list:
        try:
            ev = json.loads(raw)
            if cutoff:
                ts = datetime.fromisoformat(ev.get("created_at", "1970-01-01T00:00:00"))
                if ts < cutoff:
                    continue
            events.append(ev)
        except Exception:
            continue
    return events


# ---------------------------------------------------------------------------
# GET /api/analytics/queries
# ---------------------------------------------------------------------------

@router.get("/queries")
async def get_queries(date_range: DateRange = Query(default="30d")) -> dict:
    events = await _load_events(date_range)

    if not events:
        return {
            "query_count":          0,
            "unique_users":         0,
            "avg_response_time_ms": 0,
            "success_rate":         0.0,
            "trend":                {"data": []},
        }

    total        = len(events)
    successful   = sum(1 for e in events if e.get("success", True))
    durations    = [e["duration_ms"] for e in events if "duration_ms" in e]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0
    users        = {e.get("team_id", "unknown") for e in events}

    daily: dict[str, int] = {}
    for ev in events:
        day = ev.get("created_at", "")[:10]
        if day:
            daily[day] = daily.get(day, 0) + 1

    return {
        "query_count":          total,
        "unique_users":         len(users),
        "avg_response_time_ms": avg_duration,
        "success_rate":         round(successful / total, 3),
        "trend":                {"data": [{"date": d, "count": c} for d, c in sorted(daily.items())]},
    }


# ---------------------------------------------------------------------------
# GET /api/analytics/topics
# ---------------------------------------------------------------------------

@router.get("/topics")
async def get_topics(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    r = await _redis()
    try:
        results = await r.zrevrange("gs:topics", 0, limit - 1, withscores=True)
    except Exception as exc:
        logger.warning("topics_redis_read_failed", extra={"error": str(exc)})
        return {"topics": []}
    finally:
        await r.aclose()

    return {"topics": [{"topic": t, "count": int(c)} for t, c in results]}


# ---------------------------------------------------------------------------
# GET /api/analytics/knowledge-health
# ---------------------------------------------------------------------------

_EMPTY_DOMAINS = [
    {"domain": label, "coverage": 0.0, "freshness": 0.0, "accuracy": 0.0, "score": 0.0}
    for label in ["Service", "Library", "Incident", "Team"]
]


@router.get("/knowledge-health")
async def get_knowledge_health() -> dict:
    rows: list[dict] = []
    try:
        from graph_store.config import settings as neo4j_settings
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            neo4j_settings.neo4j_uri,
            auth=(neo4j_settings.neo4j_username, neo4j_settings.neo4j_password),
        )
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt"
            )
            rows = await result.data()
        await driver.close()
    except Exception as exc:
        logger.warning("knowledge_health_neo4j_error", extra={"error": str(exc)})

    counts: dict[str, int] = {r["label"]: r["cnt"] for r in rows if r.get("label")}
    total_nodes = sum(counts.values()) or 1

    def _score(label: str) -> dict:
        cnt      = counts.get(label, 0)
        coverage = min(1.0, cnt / max(total_nodes * 0.25, 1))
        return {
            "domain":    label,
            "coverage":  round(coverage, 2),
            "freshness": 0.85,
            "accuracy":  0.90,
            "score":     round((coverage + 0.85 + 0.90) / 3, 2),
        }

    domains = [_score(lbl) for lbl in ["Service", "Library", "Incident", "Team"] if lbl in counts]
    if not domains:
        domains = _EMPTY_DOMAINS

    overall = round(sum(d["score"] for d in domains) / len(domains), 2)
    return {"overall_score": overall, "domains": domains}


# ---------------------------------------------------------------------------
# GET /api/analytics/dependencies
# ---------------------------------------------------------------------------

@router.get("/dependencies")
async def get_dependencies() -> dict:
    rows: list[dict] = []
    try:
        from graph_store.config import settings as neo4j_settings
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            neo4j_settings.neo4j_uri,
            auth=(neo4j_settings.neo4j_username, neo4j_settings.neo4j_password),
        )
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (n)
                WHERE n:Service OR n:Library
                RETURN labels(n)[0]                          AS type,
                       n.name                                AS name,
                       coalesce(n.version, '0.0.0')          AS current_version,
                       coalesce(n.latest_version, '0.0.0')   AS latest_version,
                       coalesce(n.breaking_change, false)     AS breaking_change,
                       coalesce(n.team, 'unknown')            AS team
                LIMIT 100
                """
            )
            rows = await result.data()
        await driver.close()
    except Exception as exc:
        logger.warning("dependencies_neo4j_error", extra={"error": str(exc)})

    now = datetime.utcnow().isoformat()
    deps = []
    for r in rows:
        name = r.get("name")
        if not name:
            continue  # skip nodes without a name property
        deps.append({
            "name":            str(name),
            "type":            (r.get("type") or "service").lower(),
            "current_version": r.get("current_version", "0.0.0"),
            "latest_version":  r.get("latest_version", "0.0.0"),
            "breaking_change": bool(r.get("breaking_change", False)),
            "teams":           [str(r.get("team", "unknown"))],
            "last_checked":    now,
        })
    return {"dependencies": deps}


# ---------------------------------------------------------------------------
# GET /api/analytics/escalations
# ---------------------------------------------------------------------------

@router.get("/escalations")
async def get_escalations(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    r = await _redis()
    try:
        raw_list = await r.lrange("gs:escalations", 0, limit - 1)
        total    = await r.llen("gs:escalations")
    except Exception as exc:
        logger.warning("escalations_redis_read_failed", extra={"error": str(exc)})
        return {"escalations": [], "total": 0}
    finally:
        await r.aclose()

    escalations = []
    for raw in raw_list:
        try:
            escalations.append(json.loads(raw))
        except Exception:
            continue
    return {"escalations": escalations, "total": total}


# ---------------------------------------------------------------------------
# GET /api/analytics/export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_analytics(
    scope:      str       = Query(default="full"),
    format:     str       = Query(default="csv"),
    date_range: DateRange = Query(default="30d"),
) -> StreamingResponse:
    events = await _load_events(date_range)

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["created_at", "query", "team_id", "success", "duration_ms"],
        )
        writer.writeheader()
        for ev in events:
            writer.writerow({
                "created_at":  ev.get("created_at", ""),
                "query":       ev.get("query", ""),
                "team_id":     ev.get("team_id", ""),
                "success":     ev.get("success", True),
                "duration_ms": ev.get("duration_ms", 0),
            })
        content = buf.getvalue().encode("utf-8")
        media   = "text/csv"
        suffix  = "csv"
    else:
        # PDF renderer (e.g. weasyprint) not yet wired — return CSV fallback
        content = b"PDF export not yet implemented. Use format=csv.\n"
        media   = "text/plain"
        suffix  = "txt"

    filename = f"godspeed-{scope}-{date_range}.{suffix}"
    return StreamingResponse(
        iter([content]),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
