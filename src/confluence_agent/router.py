from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from src.confluence_agent.config import confluence_config
from src.confluence_agent.tasks import confluence_process_page, confluence_sync_space

logger = logging.getLogger(__name__)
router = APIRouter(tags=["confluence"])


def _verify_confluence_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/confluence")
async def confluence_webhook(
    request: Request,
    x_hub_signature: str = Header(default=""),
) -> dict[str, Any]:
    body = await request.body()

    if confluence_config.confluence_webhook_secret:
        if not _verify_confluence_signature(body, x_hub_signature, confluence_config.confluence_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Confluence webhook signature")

    payload = await request.json()
    event = payload.get("webhookEvent", "")

    if event not in ("page_created", "page_updated"):
        return {"status": "ignored", "event": event}

    page = payload.get("page", {})
    page_id = str(page.get("id", ""))
    space_key = (page.get("space") or {}).get("key", "")

    if not page_id:
        raise HTTPException(status_code=400, detail="Missing page.id in payload")

    task = confluence_process_page.delay(page_id, space_key, confluence_config.team_id)
    logger.info("confluence_webhook: queued task %s for page %s", task.id, page_id)
    return {"status": "accepted", "task_id": task.id, "page_id": page_id}


@router.post("/confluence/sync/{space_key}")
async def trigger_confluence_sync(space_key: str) -> dict[str, Any]:
    task = confluence_sync_space.delay(space_key, confluence_config.team_id)
    logger.info("confluence_sync: triggered full sync for space %s, task %s", space_key, task.id)
    return {"status": "accepted", "task_id": task.id, "space_key": space_key}
