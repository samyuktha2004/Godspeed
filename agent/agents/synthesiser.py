"""Synthesiser agent — merges agent results and streams a cited answer."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from agent.agents._gemini import stream_gemini_text
from agent.config import settings
from agent.models import AgentResult, RetrievedChunk
from agent.prompts import SYNTHESISER_SYSTEM_PROMPT, build_synthesiser_prompt

logger = logging.getLogger(__name__)


def _overall_confidence(agent_results: dict[str, AgentResult]) -> str:
    levels = [r.retrieval_confidence for r in agent_results.values() if r.chunks]
    if not levels:
        return "low"
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _collect_all_chunks(agent_results: dict[str, AgentResult]) -> list[RetrievedChunk]:
    seen_ids: set[str] = set()
    chunks: list[RetrievedChunk] = []
    for result in agent_results.values():
        for chunk in result.chunks:
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                chunks.append(chunk)
    return chunks


async def stream_synthesis(
    query: str,
    agent_results: dict[str, AgentResult],
) -> AsyncGenerator[str, None]:
    confidence = _overall_confidence(agent_results)
    all_chunks = _collect_all_chunks(agent_results)

    chunks_text = "\n\n".join(
        f"[{c.source}] {c.text}" for c in all_chunks
    )
    prompt = build_synthesiser_prompt(query, confidence, chunks_text)

    logger.info(
        "synthesiser: streaming answer — confidence=%s, chunks=%d",
        confidence,
        len(all_chunks),
    )

    async for token in stream_gemini_text(
        model_name=settings.synthesiser_model,
        system_prompt=SYNTHESISER_SYSTEM_PROMPT,
        user_message=prompt,
    ):
        yield token
