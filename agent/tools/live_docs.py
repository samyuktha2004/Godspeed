"""Live web documentation fetcher — Firecrawl + Tavily stub."""

from __future__ import annotations

import logging

from agent.config import settings
from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)


async def run_live_docs(query: str, team_id: str) -> list[RetrievedChunk]:
    """Stub — returns empty until FIRECRAWL_API_KEY or TAVILY_API_KEY are configured."""
    if not settings.firecrawl_api_key and not settings.tavily_api_key:
        logger.info("live_docs: no API keys configured, returning empty results")
        return []

    logger.warning("live_docs: stub returning empty results")
    return []
