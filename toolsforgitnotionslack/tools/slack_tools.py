"""
Slack tools — search, history, threads, channel metadata.
"""
import os
import httpx

SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {SLACK_TOKEN}"}


async def slack_list_channels(filter_name: str = "") -> str:
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(
            "https://slack.com/api/conversations.list",
            headers=_headers(),
            params={"types": "public_channel,private_channel",
                    "limit": 200, "exclude_archived": True},
        )
    d = r.json()
    if not d.get("ok"): return f"Slack error: {d.get('error')}"
    channels = d.get("channels", [])
    if filter_name:
        channels = [c for c in channels if filter_name.lower() in c["name"].lower()]
    if not channels: return "No channels found."
    return "\n".join(
        f"• #{c['name']}  id:{c['id']}  members:{c.get('num_members',0)}"
        + (f"  [{c['purpose']['value'][:60]}]" if c.get("purpose", {}).get("value") else "")
        for c in channels
    )


async def slack_search(query: str, channel: str = "",
                        oldest_date: str = "", latest_date: str = "",
                        count: int = 10) -> str:
    q = query
    if channel:     q = f"in:#{channel.lstrip('#')} {q}"
    if oldest_date: q += f" after:{oldest_date}"
    if latest_date: q += f" before:{latest_date}"
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(
            "https://slack.com/api/search.messages",
            headers=_headers(),
            params={"query": q, "count": min(count, 20), "highlight": False},
        )
    d = r.json()
    if not d.get("ok"): return f"Slack error: {d.get('error')}"
    matches = d.get("messages", {}).get("matches", [])
    if not matches: return "No messages found."
    parts = []
    for m in matches:
        ch   = m.get("channel", {}).get("name", "?")
        user = m.get("username", "?")
        ts   = m.get("ts", "")
        text = m.get("text", "")[:400]
        link = m.get("permalink", "")
        parts.append(f"[#{ch} | {user} | {ts}]\n{text}\n{link}")
    return "\n\n---\n\n".join(parts)


async def slack_channel_history(channel_id: str, limit: int = 20,
                                 oldest: str = "", latest: str = "") -> str:
    params: dict = {"channel": channel_id, "limit": min(limit, 50)}
    if oldest: params["oldest"] = oldest
    if latest: params["latest"] = latest
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get("https://slack.com/api/conversations.history",
                        headers=_headers(), params=params)
    d = r.json()
    if not d.get("ok"): return f"Slack error: {d.get('error')}"
    messages = d.get("messages", [])
    if not messages: return "No messages in range."
    lines = []
    for m in reversed(messages):
        reply_hint = f"  [🧵 {m['reply_count']} replies]" if m.get("reply_count") else ""
        lines.append(f"[{m.get('ts','')}] {m.get('text','')[:300]}{reply_hint}")
    return "\n".join(lines)


async def slack_get_thread(channel_id: str, thread_ts: str, limit: int = 30) -> str:
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(
            "https://slack.com/api/conversations.replies",
            headers=_headers(),
            params={"channel": channel_id, "ts": thread_ts, "limit": min(limit, 50)},
        )
    d = r.json()
    if not d.get("ok"): return f"Slack error: {d.get('error')}"
    messages = d.get("messages", [])
    if not messages: return "Thread not found or empty."
    return "\n".join(
        f"[{m.get('ts','')}] {m.get('username', m.get('user','?'))}: {m.get('text','')[:400]}"
        for m in messages
    )


# ── Registry ───────────────────────────────────────────────────────────────────

SLACK_TOOL_FNS = {
    "slack_list_channels":   slack_list_channels,
    "slack_search":          slack_search,
    "slack_channel_history": slack_channel_history,
    "slack_get_thread":      slack_get_thread,
}

SLACK_TOOLS = [
    {"type": "function", "function": {
        "name": "slack_list_channels",
        "description": (
            "List public/private Slack channels with their IDs. "
            "Call this FIRST to discover channel IDs before using slack_channel_history. "
            "Do NOT use to search messages — use slack_search for that."
        ),
        "parameters": {"type": "object", "properties": {
            "filter_name": {"type": "string", "description": "Filter channels by name substring"},
        }},
    }},
    {"type": "function", "function": {
        "name": "slack_search",
        "description": (
            "Search Slack messages across channels by topic or keyword. "
            "Supports time filtering with oldest_date/latest_date (YYYY-MM-DD). "
            "Use this for topic lookups. Use slack_channel_history for recent chronological messages."
        ),
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query":       {"type": "string"},
            "channel":     {"type": "string", "description": "Limit to #channel-name"},
            "oldest_date": {"type": "string", "description": "YYYY-MM-DD"},
            "latest_date": {"type": "string", "description": "YYYY-MM-DD"},
            "count":       {"type": "integer", "description": "Max results, default 10"},
        }},
    }},
    {"type": "function", "function": {
        "name": "slack_channel_history",
        "description": (
            "Fetch recent messages from a Slack channel by channel ID. "
            "Use slack_list_channels first to get the channel ID. "
            "oldest/latest are Unix timestamps for date range filtering."
        ),
        "parameters": {"type": "object", "required": ["channel_id"], "properties": {
            "channel_id": {"type": "string"},
            "limit":      {"type": "integer", "description": "Max messages, default 20"},
            "oldest":     {"type": "string", "description": "Unix timestamp"},
            "latest":     {"type": "string", "description": "Unix timestamp"},
        }},
    }},
    {"type": "function", "function": {
        "name": "slack_get_thread",
        "description": (
            "Reconstruct a full Slack thread given a channel_id and thread_ts (timestamp). "
            "Use this when slack_channel_history shows a message has replies. "
            "Returns all replies in chronological order."
        ),
        "parameters": {"type": "object", "required": ["channel_id", "thread_ts"], "properties": {
            "channel_id": {"type": "string"},
            "thread_ts":  {"type": "string", "description": "Timestamp of the parent message"},
            "limit":      {"type": "integer", "description": "Max replies, default 30"},
        }},
    }},
]