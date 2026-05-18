"""LLM call helper with exponential-backoff retry. Uses OpenAI when key is set, else Gemini."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import settings

logger = logging.getLogger(__name__)


def _make_llm(model_name: str, streaming: bool = False):
    openai_key = getattr(settings, "openai_api_key", "")
    if openai_key:
        from langchain_openai import ChatOpenAI
        # Map Gemini model names to OpenAI equivalents
        oai_model = "gpt-4o-mini"
        return ChatOpenAI(
            model=oai_model,
            api_key=openai_key,
            temperature=0.0,
            streaming=streaming,
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=0.0,
        streaming=streaming,
    )


async def call_gemini_text(
    model_name: str,
    system_prompt: str,
    user_message: str,
) -> str:
    llm = _make_llm(model_name)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    for attempt in range(settings.gemini_max_retries):
        try:
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as exc:
            if attempt == settings.gemini_max_retries - 1:
                logger.error("LLM call failed after %d retries: %s", settings.gemini_max_retries, exc)
                raise
            delay = settings.gemini_retry_base_delay * (2 ** attempt)
            logger.warning("LLM call attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable")


async def call_gemini_json(
    model_name: str,
    system_prompt: str,
    user_message: str,
) -> dict[str, Any]:
    raw = await call_gemini_text(model_name, system_prompt, user_message)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", exc, raw[:500])
        raise


async def stream_gemini_text(
    model_name: str,
    system_prompt: str,
    user_message: str,
):
    llm = _make_llm(model_name, streaming=True)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    for attempt in range(settings.gemini_max_retries):
        try:
            async for chunk in llm.astream(messages):
                yield chunk.content
            return
        except Exception as exc:
            if attempt == settings.gemini_max_retries - 1:
                logger.error("LLM stream failed after %d retries: %s", settings.gemini_max_retries, exc)
                raise
            delay = settings.gemini_retry_base_delay * (2 ** attempt)
            logger.warning("LLM stream attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, delay)
            await asyncio.sleep(delay)
