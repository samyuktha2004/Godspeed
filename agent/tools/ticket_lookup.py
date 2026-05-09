"""Jira ticket lookup tool — interface stub, no live credentials yet."""

from __future__ import annotations

import logging

from agent.config import settings
from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)


async def run_ticket_lookup(query: str, team_id: str) -> list[RetrievedChunk]:
    """Stub — returns empty until JIRA_BASE_URL and JIRA_API_TOKEN are configured."""
    if not settings.jira_base_url or not settings.jira_api_token:
        logger.info("ticket_lookup: Jira credentials not configured, returning empty results")
        return []

    logger.warning("ticket_lookup: stub returning empty results")
    return []
