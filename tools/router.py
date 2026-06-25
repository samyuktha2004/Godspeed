from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools.agent.cache import Cache
from tools.agent.planner import build_system_prompt
from tools.tools.github_tools import GITHUB_TOOLS, GITHUB_TOOL_FNS
from tools.tools.notion_tools import NOTION_TOOLS, NOTION_TOOL_FNS
from tools.tools.slack_tools import SLACK_TOOLS, SLACK_TOOL_FNS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])

GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o-mini"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

ALL_TOOLS = GITHUB_TOOLS + SLACK_TOOLS + NOTION_TOOLS
ALL_FNS = {**GITHUB_TOOL_FNS, **SLACK_TOOL_FNS, **NOTION_TOOL_FNS}

_tool_cache = Cache(ttl_seconds=300)
_sessions: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ToolCall(BaseModel):
    name: str
    args: dict
    result: str
    cached: bool


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    elapsed_seconds: float
    tool_calls: list[ToolCall]
    model_used: str


class ClearResponse(BaseModel):
    cleared: bool
    session_id: str


async def _dispatch(name: str, args: dict) -> tuple[str, bool]:
    key = f"{name}:{json.dumps(args, sort_keys=True)}"
    cached = _tool_cache.get(key)
    if cached:
        return cached, True
    fn = ALL_FNS.get(name)
    result = await fn(**args) if fn else f"Unknown tool: {name}"
    _tool_cache.set(key, result)
    return result, False


async def _run_agent_gemini(history: list[dict]) -> tuple[str, list[ToolCall]]:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    system = build_system_prompt(GITHUB_REPO)
    messages = [SystemMessage(content=system)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    tool_log: list[ToolCall] = []

    for _ in range(14):
        response = await llm_with_tools.ainvoke(messages)

        if not response.tool_calls:
            return response.content, tool_log

        messages.append(response)

        results = await asyncio.gather(*[
            _dispatch(tc["name"], tc["args"]) for tc in response.tool_calls
        ])

        for tc, (result, was_cached) in zip(response.tool_calls, results):
            tool_log.append(ToolCall(
                name=tc["name"], args=tc["args"],
                result=result[:500], cached=was_cached,
            ))
            messages.append(ToolMessage(tool_call_id=tc["id"], content=result))

    return "Reached reasoning limit. Try a more specific question.", tool_log


async def _run_agent_openai(history: list[dict]) -> tuple[str, list[ToolCall]]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    system = build_system_prompt(GITHUB_REPO)
    messages = [{"role": "system", "content": system}] + history
    tool_log: list[ToolCall] = []

    for _ in range(14):
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            return msg.content or "", tool_log

        messages.append(msg)

        names_and_args = [
            (tc.function.name, json.loads(tc.function.arguments)) for tc in tool_calls
        ]
        results = await asyncio.gather(*[
            _dispatch(name, args) for name, args in names_and_args
        ])

        for tc, (name, args), (result, was_cached) in zip(tool_calls, names_and_args, results):
            tool_log.append(ToolCall(name=name, args=args, result=result[:500], cached=was_cached))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "Reached reasoning limit. Try a more specific question.", tool_log


async def _run_agent(history: list[dict]) -> tuple[str, list[ToolCall], str]:
    if os.environ.get("GOOGLE_API_KEY"):
        try:
            answer, tool_log = await _run_agent_gemini(history)
            return answer, tool_log, GEMINI_MODEL
        except Exception:
            logger.exception("tools_agent: Gemini failed, falling back to OpenAI")

    if os.environ.get("OPENAI_API_KEY"):
        answer, tool_log = await _run_agent_openai(history)
        return answer, tool_log, OPENAI_MODEL

    raise RuntimeError("Neither GOOGLE_API_KEY nor OPENAI_API_KEY is configured")


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="No LLM API key configured")

    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": req.message})

    t0 = time.monotonic()
    try:
        answer, tool_log, model_used = await _run_agent(history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    history.append({"role": "assistant", "content": answer})
    if len(history) > 60:
        _sessions[session_id] = history[-60:]

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        elapsed_seconds=round(time.monotonic() - t0, 2),
        tool_calls=tool_log,
        model_used=model_used,
    )


@router.delete("/chat", response_model=ClearResponse)
async def clear_session(session_id: str):
    existed = session_id in _sessions
    _sessions.pop(session_id, None)
    _tool_cache.clear()
    return ClearResponse(cleared=existed, session_id=session_id)


@router.get("/health")
async def tools_health():
    return {
        "status": "ok",
        "primary_model": GEMINI_MODEL,
        "fallback_model": OPENAI_MODEL,
        "gemini": bool(os.environ.get("GOOGLE_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "github": bool(os.environ.get("GITHUB_TOKEN")),
        "slack": bool(os.environ.get("SLACK_BOT_TOKEN")),
        "notion": bool(os.environ.get("NOTION_API_TOKEN")),
        "active_sessions": len(_sessions),
    }
