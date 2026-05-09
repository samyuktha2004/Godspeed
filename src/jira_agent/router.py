from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from src.jira_agent.config import jira_config
from src.jira_agent.tasks import jira_process_issue, jira_sync_project

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jira"])

# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------

def _verify_jira_signature(body: bytes, signature: str, secret: str) -> bool:
    """Jira Cloud sends HMAC-SHA256 in X-Hub-Signature header."""
    if not secret:
        return True  # skip verification when secret not configured
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    x_hub_signature: str = Header(default=""),
) -> dict[str, Any]:
    body = await request.body()

    if jira_config.jira_webhook_secret:
        if not _verify_jira_signature(body, x_hub_signature, jira_config.jira_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Jira webhook signature")

    payload = await request.json()
    event = payload.get("webhookEvent", "")

    if event not in ("jira:issue_created", "jira:issue_updated"):
        return {"status": "ignored", "event": event}

    issue = payload.get("issue", {})
    issue_key = issue.get("key")
    if not issue_key:
        raise HTTPException(status_code=400, detail="Missing issue.key in payload")

    task = jira_process_issue.delay(issue_key, jira_config.team_id)
    logger.info("jira_webhook: queued task %s for issue %s", task.id, issue_key)
    return {"status": "accepted", "task_id": task.id, "issue_key": issue_key}


@router.post("/jira/sync/{project_key}")
async def trigger_jira_sync(project_key: str) -> dict[str, Any]:
    task = jira_sync_project.delay(project_key, jira_config.team_id)
    logger.info("jira_sync: triggered full sync for project %s, task %s", project_key, task.id)
    return {"status": "accepted", "task_id": task.id, "project_key": project_key}
