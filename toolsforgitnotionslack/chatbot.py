"""
FastAPI endpoint for the Enterprise Knowledge Assistant.

pip install fastapi uvicorn

Run:
    uvicorn app:app --reload --port 8000

Endpoints:
    POST /chat        — single-turn or multi-turn conversation
    DELETE /chat      — clear session history and cache
    GET  /health      — service status
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio, json, os, time, uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import AsyncOpenAI
from tools.github_tools import GITHUB_TOOLS, GITHUB_TOOL_FNS
from tools.slack_tools  import SLACK_TOOLS,  SLACK_TOOL_FNS
from tools.notion_tools import NOTION_TOOLS,  NOTION_TOOL_FNS
from agent.cache        import Cache
from agent.planner      import build_system_prompt

# ── Config ─────────────────────────────────────────────────────────────────────

MODEL       = "gpt-4o-mini"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
client      = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

ALL_TOOLS = GITHUB_TOOLS + SLACK_TOOLS + NOTION_TOOLS
ALL_FNS   = {**GITHUB_TOOL_FNS, **SLACK_TOOL_FNS, **NOTION_TOOL_FNS}

tool_cache = Cache(ttl_seconds=300)

# session_id → list of message dicts
sessions: dict[str, list[dict]] = {}

# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [v for v in ["OPENAI_API_KEY"] if not os.environ.get(v)]
    if missing:
        print(f"⚠️  Missing env vars: {', '.join(missing)}")
    print(f"  GitHub {'✓' if os.environ.get('GITHUB_TOKEN') else '✗'}  "
          f"Slack {'✓' if os.environ.get('SLACK_BOT_TOKEN') else '✗'}  "
          f"Notion {'✓' if os.environ.get('NOTION_API_TOKEN') else '✗'}")
    yield

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Enterprise Knowledge Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None   # omit to start a new session

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

class ClearResponse(BaseModel):
    cleared: bool
    session_id: str

class HealthResponse(BaseModel):
    status: str
    model: str
    github: bool
    slack: bool
    notion: bool
    active_sessions: int

# ── Agent ──────────────────────────────────────────────────────────────────────

async def dispatch(name: str, args: dict) -> tuple[str, bool]:
    """Returns (result, was_cached)."""
    key    = f"{name}:{json.dumps(args, sort_keys=True)}"
    cached = tool_cache.get(key)
    if cached:
        return cached, True
    fn     = ALL_FNS.get(name)
    result = await fn(**args) if fn else f"Unknown tool: {name}"
    tool_cache.set(key, result)
    return result, False


async def run_agent(history: list[dict]) -> tuple[str, list[ToolCall]]:
    system   = build_system_prompt(GITHUB_REPO)
    messages = [{"role": "system", "content": system}] + history
    tool_log: list[ToolCall] = []

    for _ in range(14):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg        = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            return msg.content or "", tool_log

        messages.append(msg)

        names_and_args = [
            (tc.function.name, json.loads(tc.function.arguments))
            for tc in tool_calls
        ]

        results = await asyncio.gather(*[
            dispatch(name, args) for name, args in names_and_args
        ])

        for tc, (name, args), (result, was_cached) in zip(tool_calls, names_and_args, results):
            tool_log.append(ToolCall(name=name, args=args,
                                     result=result[:500], cached=was_cached))
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })

    return "⚠️ Reached reasoning limit. Try a more specific question.", tool_log

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history    = sessions.setdefault(session_id, [])

    history.append({"role": "user", "content": req.message})

    t0 = time.monotonic()
    try:
        answer, tool_log = await run_agent(history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    history.append({"role": "assistant", "content": answer})

    # cap session size
    if len(history) > 60:
        sessions[session_id] = history[-60:]

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        elapsed_seconds=round(time.monotonic() - t0, 2),
        tool_calls=tool_log,
    )


@app.delete("/chat", response_model=ClearResponse)
async def clear_session(session_id: str):
    existed = session_id in sessions
    sessions.pop(session_id, None)
    tool_cache.clear()
    return ClearResponse(cleared=existed, session_id=session_id)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model=MODEL,
        github=bool(os.environ.get("GITHUB_TOKEN")),
        slack=bool(os.environ.get("SLACK_BOT_TOKEN")),
        notion=bool(os.environ.get("NOTION_API_TOKEN")),
        active_sessions=len(sessions),
    )