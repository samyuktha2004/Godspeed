"""Guardrail agent — checks answer groundedness, returns confidence score."""

from __future__ import annotations

import logging
from typing import Optional

from agent.agents._gemini import call_gemini_json
from agent.config import settings
from agent.models import RetrievedChunk
from agent.prompts import GUARDRAIL_SYSTEM_PROMPT, build_guardrail_prompt

logger = logging.getLogger(__name__)


async def run_guardrail(
    answer: str,
    chunks: list[RetrievedChunk],
) -> tuple[float, bool]:
    """Returns (score, escalate) — score in [0,1], escalate True if score < 0.5."""
    if not answer.strip():
        logger.warning("guardrail: empty answer received, escalating")
        return 0.0, True

    chunks_text = "\n\n".join(
        f"[{c.source}] {c.text}" for c in chunks
    )
    prompt = build_guardrail_prompt(answer, chunks_text)

    try:
        data = await call_gemini_json(
            model_name=settings.guardrail_model,
            system_prompt=GUARDRAIL_SYSTEM_PROMPT,
            user_message=prompt,
        )
        score = float(data.get("score", 0.0))
        escalate = bool(data.get("escalate", score < 0.5))
        logger.info("guardrail: score=%.3f escalate=%s reasoning=%r", score, escalate, data.get("reasoning"))
        return score, escalate
    except Exception:
        logger.exception("guardrail: evaluation failed — escalating by default")
        return 0.0, True
