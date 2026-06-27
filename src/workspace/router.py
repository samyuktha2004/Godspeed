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
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# GET /api/workspace/history
# ---------------------------------------------------------------------------

@router.get("/api/workspace/history")
async def get_history(
    page:  int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    is_admin = user.get("role") == "admin"
    user_id  = user.get("id")

    r = await _redis()
    try:
        # Admins get the full list via Redis offset; non-admins filter in Python
        if is_admin:
            total    = await r.llen(HISTORY_KEY)
            start    = (page - 1) * limit
            raw_list = await r.lrange(HISTORY_KEY, start, start + limit - 1)
        else:
            raw_list = await r.lrange(HISTORY_KEY, 0, 9999)
    except Exception as exc:
        logger.warning("workspace_history_redis_failed", extra={"error": str(exc)})
        return {"items": [], "total": 0}
    finally:
        await r.aclose()

    items = []
    for raw in raw_list:
        try:
            ev = json.loads(raw)
            if not is_admin and ev.get("user_id") != user_id:
                continue
            items.append({
                "id":           ev.get("id", ""),
                "query":        ev.get("query", ""),
                "answer_brief": ev.get("answer_brief", ""),
                "created_at":   ev.get("created_at", ""),
                "success":      ev.get("success", True),
                "duration_ms":  ev.get("duration_ms", 0),
            })
        except Exception:
            continue

    if not is_admin:
        total = len(items)
        start = (page - 1) * limit
        items = items[start: start + limit]

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# POST /api/query/{query_id}/feedback
# ---------------------------------------------------------------------------

Sentiment = Literal["helpful", "not_helpful", "hallucinated"]


class FeedbackBody(BaseModel):
    sentiment: Sentiment
    text:      str | None = None


@router.post("/api/query/{query_id}/feedback")
async def post_feedback(query_id: str, body: FeedbackBody, user: dict = Depends(get_current_user)) -> dict:
    r = await _redis()
    try:
        key     = FEEDBACK_KEY.format(id=query_id)
        payload = {"sentiment": body.sentiment, "text": body.text or ""}
        await r.set(key, json.dumps(payload), ex=86400 * 30)
    except Exception as exc:
        logger.warning("workspace_feedback_redis_failed", extra={"query_id": query_id, "error": str(exc)})
    finally:
        await r.aclose()

    logger.info("feedback_received", extra={"query_id": query_id, "sentiment": body.sentiment})
    return {"ok": True}
