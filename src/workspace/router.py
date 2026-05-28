"""Workspace API — query history and feedback, stored in Redis."""

from __future__ import annotations

import json
from typing import Literal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.auth.deps import get_current_user
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["workspace"])

HISTORY_KEY  = "gs:queries"       # shared with analytics
FEEDBACK_KEY = "gs:feedback:{id}" # one key per query_id


async def _redis() -> aioredis.Redis:
    # Delegates to the process-wide singleton — see src/utils/clients.py.
    # Do NOT call aclose() on the returned client.
    from src.utils.clients import get_redis
    return await get_redis()


# ---------------------------------------------------------------------------
# GET /api/workspace/history
# ---------------------------------------------------------------------------

@router.get("/api/workspace/history")
async def get_history(
    page:  int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        r = await _redis()
        # Pull a wider slice so we can filter by team before paging.
        # gs:queries is trimmed to 1000 in agent/api.py, so this is bounded.
        raw_list = await r.lrange(HISTORY_KEY, 0, 999)
    except Exception as exc:
        logger.warning("workspace_history_redis_failed", extra={"error": str(exc)})
        return {"items": [], "total": 0}

    is_admin = user.get("role") in ("admin", "org_admin")
    user_team_id = user.get("team_id")

    visible: list[dict] = []
    for raw in raw_list:
        try:
            ev = json.loads(raw)
        except Exception:
            continue
        if not is_admin and ev.get("team_id") != user_team_id:
            continue
        visible.append(ev)

    total = len(visible)
    start = (page - 1) * limit
    page_slice = visible[start : start + limit]

    items = [
        {
            "id":           ev.get("id", ""),
            "query":        ev.get("query", ""),
            "answer_brief": ev.get("answer_brief", ""),
            "created_at":   ev.get("created_at", ""),
            "success":      ev.get("success", True),
            "duration_ms":  ev.get("duration_ms", 0),
        }
        for ev in page_slice
    ]

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# POST /api/query/{query_id}/feedback
# ---------------------------------------------------------------------------

Sentiment = Literal["helpful", "not_helpful", "hallucinated"]


class FeedbackBody(BaseModel):
    sentiment: Sentiment
    text:      str | None = None


@router.post("/api/query/{query_id}/feedback")
async def post_feedback(
    query_id: str,
    body: FeedbackBody,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        r = await _redis()
        key     = FEEDBACK_KEY.format(id=query_id)
        payload = {
            "sentiment": body.sentiment,
            "text":      body.text or "",
            "user_id":   user.get("id"),
            "team_id":   user.get("team_id"),
        }
        await r.set(key, json.dumps(payload), ex=86400 * 30)
    except Exception as exc:
        logger.warning("workspace_feedback_redis_failed", extra={"query_id": query_id, "error": str(exc)})

    logger.info(
        "feedback_received",
        extra={"query_id": query_id, "sentiment": body.sentiment, "user_id": user.get("id")},
    )
    return {"ok": True}
