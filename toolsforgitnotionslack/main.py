"""
Enterprise Knowledge Assistant
GPT-4o-mini orchestrated, MCP-style tool calling across GitHub, Slack, Notion.

pip install openai httpx python-dotenv

.env:
  OPENAI_API_KEY=
  GITHUB_TOKEN=       # free PAT with repo read scope
  GITHUB_REPO=        # default "owner/repo" (optional)
  SLACK_BOT_TOKEN=    # free workspace bot token
  NOTION_API_TOKEN=   # free integration token
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio, json, os, time
from openai import AsyncOpenAI
from tools.github_tools import GITHUB_TOOLS, GITHUB_TOOL_FNS
from tools.slack_tools  import SLACK_TOOLS,  SLACK_TOOL_FNS
from tools.notion_tools import NOTION_TOOLS,  NOTION_TOOL_FNS
from agent.cache        import Cache
from agent.planner      import build_system_prompt

MODEL       = "gpt-4o-mini"
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
client      = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# ALL_TOOLS = GITHUB_TOOLS+ NOTION_TOOLS
# ALL_FNS = {**GITHUB_TOOL_FNS,**NOTION_TOOL_FNS}
ALL_TOOLS   = GITHUB_TOOLS + SLACK_TOOLS + NOTION_TOOLS
ALL_FNS     = {**GITHUB_TOOL_FNS, **SLACK_TOOL_FNS, **NOTION_TOOL_FNS}
cache       = Cache(ttl_seconds=300)


async def dispatch(name: str, args: dict) -> str:
    key    = f"{name}:{json.dumps(args, sort_keys=True)}"
    cached = cache.get(key)
    if cached:
        return f"[cached] {cached}"
    fn     = ALL_FNS.get(name)
    result = await fn(**args) if fn else f"Unknown tool: {name}"
    cache.set(key, result)
    return result


async def run_agent(history: list[dict]) -> str:
    system = build_system_prompt(GITHUB_REPO)
    messages = [{"role": "system", "content": system}] + history

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
            return msg.content or ""

        messages.append(msg)

        results = await asyncio.gather(*[
            dispatch(tc.function.name, json.loads(tc.function.arguments))
            for tc in tool_calls
        ])

        for tc, result in zip(tool_calls, results):
            tag = " [cached]" if result.startswith("[cached]") else ""
            print(f"  🔧 {tc.function.name}{tag} → {result[:90].replace(chr(10),' ')}…")
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      result,
            })

    return "⚠️ Reached reasoning limit. Try a more specific question."


async def chat_loop():
    history: list[dict] = []
    print(f"\n{'═'*60}\n  Enterprise Knowledge Assistant  |  {MODEL}")
    print(f"  GitHub {'✓' if os.environ.get('GITHUB_TOKEN') else '✗'}  "
          f"Slack {'✓' if os.environ.get('SLACK_BOT_TOKEN') else '✗'}  "
          f"Notion {'✓' if os.environ.get('NOTION_API_TOKEN') else '✗'}")
    if GITHUB_REPO:
        print(f"  Default repo: {GITHUB_REPO}")
    print(f"{'═'*60}\nCommands: /clear  /quit\n")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye!"); break
        if not user: continue
        if user.lower() in ("/quit", "/exit"):
            print("👋 Bye!"); break
        if user.lower() == "/clear":
            history = []; cache.clear()
            print("🗑️  Cleared.\n"); continue

        history.append({"role": "user", "content": user})
        t0 = time.monotonic()
        try:
            answer = await run_agent(history)
        except Exception as e:
            answer = f"❌ {e}"

        history.append({"role": "assistant", "content": answer})
        print(f"\nAssistant ({time.monotonic()-t0:.1f}s):\n{answer}\n{'─'*60}")
        if len(history) > 60:
            history = history[-60:]


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Missing OPENAI_API_KEY")
    asyncio.run(chat_loop())