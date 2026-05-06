"""Summariser tool — condenses large chunk sets using Gemini Flash."""

from __future__ import annotations

import logging

from agent.config import settings
from agent.models import RetrievedChunk
from agent.prompts import build_summariser_prompt

logger = logging.getLogger(__name__)


async def run_summariser(chunks: list[RetrievedChunk], query: str) -> str:
    from agent.agents._gemini import call_gemini_text

    if not chunks:
        return ""

    chunks_text = "\n\n".join(
        f"[{c.source}] {c.text}" for c in chunks
    )
    prompt = build_summariser_prompt(chunks_text, query)

    summary = await call_gemini_text(
        model_name=settings.summariser_model,
        system_prompt="You are a concise technical summariser. Summarise only what is in the provided text.",
        user_message=prompt,
    )
    logger.info("summariser: produced %d-char summary", len(summary))
    return summary
