"""Shared Gemini call helper with exponential-backoff retry."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import settings

logger = logging.getLogger(__name__)


async def call_gemini_text(
    model_name: str,
    system_prompt: str,
    user_message: str,
) -> str:
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=0.0,
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    for attempt in range(settings.gemini_max_retries):
        try:
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as exc:
            if attempt == settings.gemini_max_retries - 1:
                logger.error("Gemini call failed after %d retries: %s", settings.gemini_max_retries, exc)
                raise
            delay = settings.gemini_retry_base_delay * (2 ** attempt)
            logger.warning("Gemini call attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable")


async def call_gemini_json(
    model_name: str,
    system_prompt: str,
    user_message: str,
) -> dict[str, Any]:
    raw = await call_gemini_text(model_name, system_prompt, user_message)
    # Strip markdown code fences if model ignores the instruction
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini JSON response: %s\nRaw: %s", exc, raw[:500])
        raise


async def stream_gemini_text(
    model_name: str,
    system_prompt: str,
    user_message: str,
):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=0.0,
        streaming=True,
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    for attempt in range(settings.gemini_max_retries):
        try:
            async for chunk in llm.astream(messages):
                yield chunk.content
            return
        except Exception as exc:
            if attempt == settings.gemini_max_retries - 1:
                logger.error("Gemini stream failed after %d retries: %s", settings.gemini_max_retries, exc)
                raise
            delay = settings.gemini_retry_base_delay * (2 ** attempt)
            logger.warning("Gemini stream attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
            await asyncio.sleep(delay)
