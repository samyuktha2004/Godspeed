"""
GitHub tools — discovery-first, markdown-only reads, paginated, rate-limit aware.
"""
import os
import httpx

GH           = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")


def _headers() -> dict:
    return {
        "Authorization":        f"Bearer {GITHUB_TOKEN}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _target(repo: str) -> str:
    return repo or GITHUB_REPO


def _rate_warn(resp: httpx.Response) -> str | None:
    if resp.headers.get("x-ratelimit-remaining", "1") == "0":
        reset = resp.headers.get("x-ratelimit-reset", "soon")
        return f"⚠️ GitHub rate limit reached. Resets at epoch {reset}."
    return None


# ── Tools ──────────────────────────────────────────────────────────────────────

async def github_list_repos(org_or_user: str = "", repo_type: str = "all",
                             page: int = 1) -> str:
    params = {"type": repo_type, "per_page": 50, "page": page}
    async with httpx.AsyncClient(timeout=15) as h:
        if org_or_user:
            r = await h.get(f"{GH}/orgs/{org_or_user}/repos",
                            headers=_headers(), params=params)
            if r.status_code == 404:
                r = await h.get(f"{GH}/users/{org_or_user}/repos",
                                headers=_headers(), params=params)
        else:
            r = await h.get(f"{GH}/user/repos", headers=_headers(), params=params)
    if w := _rate_warn(r): return w
    if r.status_code != 200: return f"GitHub error {r.status_code}: {r.text[:300]}"
    repos = r.json()
    if not repos: return "No repositories found."
    lines = [
        f"• {repo['full_name']}  {'🔒' if repo['private'] else '🌐'}  "
        f"⭐{repo['stargazers_count']}  {(repo.get('description') or '')[:80]}"
        for repo in repos
    ]
    if len(repos) == 50:
        lines.append(f"[Page {page} — call with page={page+1} for more]")
    return "\n".join(lines)


async def github_repo_summary(repo: str = "") -> str:
    t = _target(repo)
    if not t: return "Provide repo as 'owner/repo' or set GITHUB_REPO."
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(f"{GH}/repos/{t}", headers=_headers())
    if w := _rate_warn(r): return w
    if r.status_code == 404: return f"Repo not found: {t}"
    if r.status_code != 200: return f"GitHub error {r.status_code}"
    d = r.json()
    topics = ", ".join(d.get("topics", [])) or "none"
    return (
        f"Repo: {d['full_name']}\n"
        f"Description: {d.get('description') or 'n/a'}\n"
        f"Language: {d.get('language') or 'n/a'}\n"
        f"Topics: {topics}\n"
        f"Default branch: {d.get('default_branch')}\n"
        f"Stars: {d['stargazers_count']}  Open issues: {d['open_issues_count']}\n"
        f"URL: {d['html_url']}"
    )


async def github_list_files(repo: str = "", path: str = "", branch: str = "") -> str:
    t = _target(repo)
    if not t: return "Provide repo as 'owner/repo' or set GITHUB_REPO."
    params = {"ref": branch} if branch else {}
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(f"{GH}/repos/{t}/contents/{path}",
                        headers=_headers(), params=params)
    if w := _rate_warn(r): return w
    if r.status_code == 404: return f"Path '{path}' not found in {t}."
    if r.status_code != 200: return f"GitHub error {r.status_code}"
    items = r.json()
    if isinstance(items, dict):
        return f"'{path}' is a file. Use github_read_file to read it."
    lines = []
    for item in sorted(items, key=lambda x: (x["type"] != "dir", x["name"])):
        icon = "📁" if item["type"] == "dir" else "📄"
        size = f"  {item.get('size',0):,}b" if item["type"] == "file" else ""
        lines.append(f"{icon} {item['path']}{size}")
    return "\n".join(lines) or "Empty directory."


async def github_read_file(path: str, repo: str = "", branch: str = "") -> str:
    t = _target(repo)
    if not t: return "Provide repo as 'owner/repo' or set GITHUB_REPO."
    lower = path.lower()
    allowed_exts  = (".md", ".mdx", ".txt", ".rst", ".adoc")
    allowed_names = ("readme", "changelog", "contributing", "license", "notice")
    allowed_dirs  = ("docs/", "doc/", "wiki/", "adr/", "architecture/", "rfcs/")
    is_doc = (
        any(lower.endswith(e) for e in allowed_exts)
        or any(os.path.basename(lower) == n for n in allowed_names)
        or any(lower.startswith(d) for d in allowed_dirs)
    )
    if not is_doc:
        return (
            f"⚠️ '{path}' looks like a source/config file. "
            "This tool is for documentation only (.md, README, docs/ etc). "
            "Re-call with the same args only if the user explicitly asked for this file."
        )
    params = {"ref": branch} if branch else {}
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(
            f"{GH}/repos/{t}/contents/{path}",
            headers={**_headers(), "Accept": "application/vnd.github.raw+json"},
            params=params,
        )
    if w := _rate_warn(r): return w
    if r.status_code == 404: return f"File not found: {path} in {t}"
    if r.status_code != 200: return f"GitHub error {r.status_code}"
    content = r.text
    total   = len(content)
    if total > 8000:
        content = content[:8000] + f"\n\n…[truncated — {total:,} chars total]"
    return f"[{t} · {path}]\n\n{content}"


async def github_search_code(query: str, repo: str = "", language: str = "",
                              path_filter: str = "") -> str:
    t = _target(repo)
    q = query
    if t:           q += f" repo:{t}"
    if language:    q += f" language:{language}"
    if path_filter: q += f" path:{path_filter}"
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(f"{GH}/search/code", headers=_headers(),
                        params={"q": q, "per_page": 10})
    if w := _rate_warn(r): return w
    if r.status_code == 422: return "Search query too short or invalid."
    if r.status_code == 403: return "GitHub search rate limit hit. Wait 60s then retry."
    if r.status_code != 200: return f"GitHub error {r.status_code}: {r.text[:200]}"
    items = r.json().get("items", [])
    if not items: return "No matching files found."
    return "\n".join(
        f"• {i['repository']['full_name']}/{i['path']}\n  {i['html_url']}"
        for i in items
    )


async def github_list_markdown_files(repo: str = "", folder: str = "") -> str:
    t = _target(repo)
    if not t: return "Provide repo as 'owner/repo' or set GITHUB_REPO."
    q = f"extension:md repo:{t}"
    if folder: q += f" path:{folder}"
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(f"{GH}/search/code", headers=_headers(),
                        params={"q": q, "per_page": 30})
    if w := _rate_warn(r): return w
    if r.status_code != 200: return f"GitHub error {r.status_code}"
    items = r.json().get("items", [])
    if not items: return "No markdown files found."
    return f"[{t}] {len(items)} markdown file(s):\n" + "\n".join(f"• {i['path']}" for i in items)


# ── Registry ───────────────────────────────────────────────────────────────────

GITHUB_TOOL_FNS = {
    "github_list_repos":          github_list_repos,
    "github_repo_summary":        github_repo_summary,
    "github_list_files":          github_list_files,
    "github_read_file":           github_read_file,
    "github_search_code":         github_search_code,
    "github_list_markdown_files": github_list_markdown_files,
}

GITHUB_TOOLS = [
    {"type": "function", "function": {
        "name": "github_list_repos",
        "description": (
            "List GitHub repositories for a user or org. "
            "Call this FIRST when you don't know which repos exist. "
            "Supports pagination. Do NOT call if you already have the repo name."
        ),
        "parameters": {"type": "object", "properties": {
            "org_or_user": {"type": "string", "description": "GitHub username or org. Empty = authenticated user."},
            "repo_type":   {"type": "string", "enum": ["all","public","private","forks","sources"]},
            "page":        {"type": "integer", "description": "Page number, default 1"},
        }},
    }},
    {"type": "function", "function": {
        "name": "github_repo_summary",
        "description": (
            "Get lightweight repo metadata: description, language, topics, stars, open issues. "
            "Call this INSTEAD of reading README when you just need a quick overview. "
            "Much cheaper than github_read_file."
        ),
        "parameters": {"type": "object", "properties": {
            "repo": {"type": "string", "description": "owner/repo"},
        }},
    }},
    {"type": "function", "function": {
        "name": "github_list_files",
        "description": (
            "List files and directories in a repo path. "
            "Use this to explore repo structure BEFORE reading any file. "
            "Do NOT use to read file content — use github_read_file for that."
        ),
        "parameters": {"type": "object", "properties": {
            "repo":   {"type": "string"}, "path": {"type": "string"},
            "branch": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "github_read_file",
        "description": (
            "Read a file from GitHub. ONLY for documentation files: "
            ".md .mdx .txt .rst, README, CHANGELOG, files in docs/ wiki/ adr/ architecture/. "
            "Do NOT use for .py .ts .json .yaml .lock source files unless user explicitly asks."
        ),
        "parameters": {"type": "object", "required": ["path"], "properties": {
            "path":   {"type": "string"}, "repo": {"type": "string"},
            "branch": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "github_search_code",
        "description": (
            "Search for text or code within GitHub repos. "
            "Use to LOCATE relevant files before reading them. "
            "Set language='markdown' and path_filter='docs/' to target documentation."
        ),
        "parameters": {"type": "object", "required": ["query"], "properties": {
            "query":       {"type": "string"}, "repo":        {"type": "string"},
            "language":    {"type": "string"}, "path_filter": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "github_list_markdown_files",
        "description": (
            "List ALL markdown (.md) files in a repo, optionally scoped to a folder. "
            "Use for documentation discovery before github_read_file. "
            "Returns file paths only, not content."
        ),
        "parameters": {"type": "object", "properties": {
            "repo":   {"type": "string"}, "folder": {"type": "string"},
        }},
    }},
]