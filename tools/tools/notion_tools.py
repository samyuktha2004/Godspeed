"""
Notion tools — search, read pages, list and query databases.
"""
import os
import httpx
def _notion_headers() -> dict:
    return {
        "Authorization":  f"Bearer {os.environ.get('NOTION_API_TOKEN', '')}",
        "Notion-Version": "2022-06-28",
        "Content-Type":   "application/json",
    }


def _extract_rich_text(rt: list) -> str:
    return "".join(t.get("plain_text", "") for t in rt)


async def notion_search(query: str, filter_type: str = "") -> str:
    body: dict = {"query": query, "page_size": 10}
    if filter_type in ("page", "database"):
        body["filter"] = {"value": filter_type, "property": "object"}
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post("https://api.notion.com/v1/search",
                         headers=_notion_headers(), json=body)
    if r.status_code != 200: return f"Notion error {r.status_code}: {r.text[:300]}"
    results = r.json().get("results", [])
    if not results: return "No Notion pages or databases found."
    out = []
    for item in results:
        obj   = item.get("object", "")
        iid   = item.get("id", "")
        url   = item.get("url", "")
        title = "Untitled"
        if obj == "page":
            for prop in item.get("properties", {}).values():
                if prop.get("type") == "title":
                    title = _extract_rich_text(prop.get("title", [])) or "Untitled"
                    break
        elif obj == "database":
            title = _extract_rich_text(item.get("title", [])) or "Untitled DB"
        out.append(f"• [{obj}] {title}\n  id: {iid}\n  {url}")
    return "\n\n".join(out)


async def notion_read_page(page_id: str, max_blocks: int = 80) -> str:
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_notion_headers(),
            params={"page_size": max_blocks},
        )
    if r.status_code != 200: return f"Notion error {r.status_code}: {r.text[:300]}"
    blocks = r.json().get("results", [])
    PREFIXES = {
        "heading_1":           "# ",
        "heading_2":           "## ",
        "heading_3":           "### ",
        "bulleted_list_item":  "• ",
        "numbered_list_item":  "1. ",
        "to_do":               "☐ ",
        "toggle":              "▶ ",
        "quote":               "> ",
        "callout":             "💡 ",
        "code":                "```\n",
    }
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        data  = block.get(btype, {})
        rt    = data.get("rich_text", [])
        text  = _extract_rich_text(rt)
        if not text and btype not in ("divider", "image"):
            continue
        if btype == "divider":
            lines.append("---")
        elif btype == "image":
            url = data.get("external", {}).get("url") or data.get("file", {}).get("url", "")
            lines.append(f"[image: {url}]")
        else:
            prefix = PREFIXES.get(btype, "")
            suffix = "\n```" if btype == "code" else ""
            lines.append(f"{prefix}{text}{suffix}")
    return "\n".join(lines) or "Page is empty or has unsupported block types."


async def notion_list_databases(query: str = "") -> str:
    body: dict = {"filter": {"value": "database", "property": "object"}, "page_size": 20}
    if query: body["query"] = query
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post("https://api.notion.com/v1/search",
                         headers=_notion_headers(), json=body)
    if r.status_code != 200: return f"Notion error {r.status_code}: {r.text[:300]}"
    results = r.json().get("results", [])
    if not results: return "No databases found."
    return "\n".join(
        f"• {_extract_rich_text(db.get('title', [])) or 'Untitled'}  id:{db['id']}"
        for db in results
    )


async def notion_query_database(database_id: str, filter_property: str = "",
                                 filter_value: str = "", page_size: int = 20) -> str:
    body: dict = {"page_size": min(page_size, 50)}
    if filter_property and filter_value:
        body["filter"] = {
            "property":  filter_property,
            "rich_text": {"contains": filter_value},
        }
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=_notion_headers(), json=body,
        )
    if r.status_code != 200: return f"Notion error {r.status_code}: {r.text[:300]}"
    results = r.json().get("results", [])
    if not results: return "No results found."
    rows = []
    for page in results:
        row = {}
        for name, prop in page.get("properties", {}).items():
            ptype = prop.get("type")
            if ptype == "title":
                row[name] = _extract_rich_text(prop.get("title", []))
            elif ptype == "rich_text":
                row[name] = _extract_rich_text(prop.get("rich_text", []))
            elif ptype == "select":
                row[name] = (prop.get("select") or {}).get("name", "")
            elif ptype == "multi_select":
                row[name] = ", ".join(s["name"] for s in prop.get("multi_select", []))
            elif ptype == "number":
                row[name] = prop.get("number", "")
            elif ptype == "checkbox":
                row[name] = "✓" if prop.get("checkbox") else "✗"
            elif ptype == "date":
                row[name] = (prop.get("date") or {}).get("start", "")
            elif ptype == "people":
                row[name] = ", ".join(p.get("name", "") for p in prop.get("people", []))
        rows.append("  ".join(f"{k}: {v}" for k, v in row.items() if v))
    return "\n".join(rows)


# ── Registry ───────────────────────────────────────────────────────────────────

NOTION_TOOL_FNS = {
    "notion_search":          notion_search,
    "notion_read_page":       notion_read_page,
    "notion_list_databases":  notion_list_databases,
    "notion_query_database":  notion_query_database,
}

NOTION_TOOLS = [
    {"type": "function", "function": {
        "name": "notion_search",
        "description": (
            "Search Notion for pages and databases by keyword. "
            "Always call this FIRST to get page IDs before calling notion_read_page. "
            "filter_type: 'page' or 'database'. Omit to search both."
        ),
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query":       {"type": "string"},
            "filter_type": {"type": "string", "enum": ["page", "database"]},
        }},
    }},
    {"type": "function", "function": {
        "name": "notion_read_page",
        "description": (
            "Read the full content of a Notion page by its ID. "
            "Only call this AFTER getting a page_id from notion_search. "
            "Preserves heading hierarchy, bullets, to-dos, callouts, code blocks."
        ),
        "parameters": {"type": "object", "required": ["page_id"], "properties": {
            "page_id":    {"type": "string"},
            "max_blocks": {"type": "integer", "description": "Max blocks to read, default 80"},
        }},
    }},
    {"type": "function", "function": {
        "name": "notion_list_databases",
        "description": (
            "List accessible Notion databases, optionally filtered by name. "
            "Use this before notion_query_database to find the correct database_id."
        ),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Filter by database name"},
        }},
    }},
    {"type": "function", "function": {
        "name": "notion_query_database",
        "description": (
            "Query rows from a Notion database. Supports text property filtering. "
            "Use notion_list_databases first to get the database_id. "
            "Extracts title, text, select, multi_select, number, checkbox, date, people fields."
        ),
        "parameters": {"type": "object", "required": ["database_id"], "properties": {
            "database_id":      {"type": "string"},
            "filter_property":  {"type": "string", "description": "Property name to filter on e.g. 'Status'"},
            "filter_value":     {"type": "string", "description": "Value to match e.g. 'Done'"},
            "page_size":        {"type": "integer", "description": "Rows to return, default 20"},
        }},
    }},
]