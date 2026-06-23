"""Slack search — searches conversation history using bot token (search.messages requires user token)."""

from __future__ import annotations

import logging
import os

import httpx

from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)


async def run_slack_search(query: str, team_id: str) -> list[RetrievedChunk]:
    """Search Slack message history for the query by scanning channels the bot is in."""
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        logger.warning("slack_search: SLACK_BOT_TOKEN not set")
        return []

    keywords = [w.lower() for w in query.split() if len(w) > 3]
    if not keywords:
        keywords = query.lower().split()

    try:
        async with httpx.AsyncClient(timeout=15) as h:
            # Get channels the bot is a member of
            r = await h.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {token}"},
                params={"types": "public_channel,private_channel", "limit": 200, "exclude_archived": True},
            )
        data = r.json()
        if not data.get("ok"):
            logger.warning("slack_search: conversations.list error: %s", data.get("error"))
            return []

        channels = [c for c in data.get("channels", []) if c.get("is_member")]
        if not channels:
            logger.info("slack_search: bot is not a member of any channels")
            return []

        chunks: list[RetrievedChunk] = []

        for ch in channels[:10]:  # cap at 10 channels
            ch_id   = ch["id"]
            ch_name = ch.get("name", ch_id)
            try:
                async with httpx.AsyncClient(timeout=15) as h:
                    r = await h.get(
                        "https://slack.com/api/conversations.history",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"channel": ch_id, "limit": 200},
                    )
                msgs = r.json().get("messages", [])
            except Exception:
                continue

            for m in msgs:
                text = m.get("text", "")
                if not text:
                    continue
                text_lower = text.lower()
                if any(kw in text_lower for kw in keywords):
                    ts   = m.get("ts", "")
                    user = m.get("user", m.get("username", "unknown"))
                    link = f"https://slack.com/archives/{ch_id}/p{ts.replace('.', '')}"
                    chunks.append(RetrievedChunk(
                        chunk_id=f"slack-{ch_id}-{ts}",
                        text=f"[#{ch_name}] {text}",
                        source=link,
                        source_type="slack",
                        score=1.0,
                        title=f"#{ch_name}",
                    ))
                    if len(chunks) >= 10:
                        break
            if len(chunks) >= 10:
                break

        logger.info("slack_search: found %d messages for query=%r", len(chunks), query)
        return chunks

    except Exception:
        logger.exception("slack_search: search failed")
        return []
