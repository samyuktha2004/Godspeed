"""Admin API — data source management, stored in Redis."""

from __future__ import annotations

import json
import os

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.deps import require_role
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

REDIS_SOURCES_KEY = "gs:data_sources"


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Seed defaults from environment on first call
# ---------------------------------------------------------------------------

def _default_sources() -> list[dict]:
    """Build source list from env vars that are set."""
    sources = []
    jira_url = os.getenv("JIRA_BASE_URL") or os.getenv("JIRA_INSTANCE_URL") or settings.integrations.jira_instance_url
    if jira_url:
        sources.append({
            "id":          "jira-default",
            "type":        "jira",
            "name":        "Jira",
            "url":         jira_url,
            "enabled":     bool(os.getenv("JIRA_API_TOKEN") or settings.integrations.jira_api_token),
            "last_sync":   None,
            "sync_status": "idle",
            "error_msg":   None,
        })
    confluence_url = os.getenv("CONFLUENCE_BASE_URL") or os.getenv("CONFLUENCE_URL")
    if confluence_url:
        sources.append({
            "id":          "confluence-default",
            "type":        "confluence",
            "name":        "Confluence",
            "url":         confluence_url,
            "enabled":     bool(os.getenv("CONFLUENCE_TOKEN") or os.getenv("CONFLUENCE_API_TOKEN")),
            "last_sync":   None,
            "sync_status": "idle",
            "error_msg":   None,
        })
    if os.getenv("GITHUB_TOKEN") or settings.integrations.github_token:
        sources.append({
            "id":          "github-default",
            "type":        "github",
            "name":        "GitHub",
            "url":         "https://github.com",
            "enabled":     bool(settings.integrations.github_token),
            "last_sync":   None,
            "sync_status": "idle",
            "error_msg":   None,
        })
    if os.getenv("SLACK_BOT_TOKEN") or settings.integrations.slack_bot_token:
        sources.append({
            "id":          "slack-default",
            "type":        "slack",
            "name":        "Slack",
            "url":         "https://slack.com",
            "enabled":     bool(settings.integrations.slack_bot_token),
            "last_sync":   None,
            "sync_status": "idle",
            "error_msg":   None,
        })
    return sources


async def _load_sources() -> list[dict]:
    r = await _redis()
    try:
        raw = await r.get(REDIS_SOURCES_KEY)
        if raw:
            return json.loads(raw)
        sources = _default_sources()
        await r.set(REDIS_SOURCES_KEY, json.dumps(sources))
        return sources
    except Exception as exc:
        logger.warning("admin_load_sources_failed", extra={"error": str(exc)})
        return _default_sources()
    finally:
        await r.aclose()


async def _save_sources(sources: list[dict]) -> None:
    r = await _redis()
    try:
        await r.set(REDIS_SOURCES_KEY, json.dumps(sources))
    except Exception as exc:
        logger.warning("admin_save_sources_failed", extra={"error": str(exc)})
    finally:
        await r.aclose()


async def update_source_sync_status(
    source_type: str,
    status: str,
    error_msg: str | None = None,
) -> None:
    """Update sync_status and last_sync for all sources matching source_type."""
    from datetime import datetime
    sources = await _load_sources()
    now = datetime.utcnow().isoformat()
    for src in sources:
        if src.get("type") == source_type:
            src["sync_status"] = status
            src["last_sync"]   = now
            src["error_msg"]   = error_msg
    await _save_sources(sources)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/data-sources")
async def list_data_sources(user=Depends(require_role("admin", "org_admin"))) -> dict:
    return {"sources": await _load_sources()}


class PatchSourceBody(BaseModel):
    enabled: bool


@router.patch("/data-sources/{source_id}")
async def patch_data_source(
    source_id: str,
    body: PatchSourceBody,
    user=Depends(require_role("admin", "org_admin")),
) -> dict:
    sources = await _load_sources()
    for src in sources:
        if src["id"] == source_id:
            src["enabled"] = body.enabled
            await _save_sources(sources)
            logger.info("data_source_toggled", extra={"id": source_id, "enabled": body.enabled})
            try:
                from src.ws.router import broadcast_notification
                await broadcast_notification({
                    "type":    "source_toggled",
                    "id":      source_id,
                    "name":    src.get("name"),
                    "enabled": body.enabled,
                })
            except Exception:
                pass
            return {"ok": True, "source": src}
    raise HTTPException(status_code=404, detail=f"Data source '{source_id}' not found")
