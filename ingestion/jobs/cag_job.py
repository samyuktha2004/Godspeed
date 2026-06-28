from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from ingestion.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)

_CAG_SYSTEM_PROMPT = """You are a technical project analyst for an enterprise engineering team.

Given a team's recent Jira activity and GitHub commits from the last 14 days, produce a structured project snapshot.

Return a JSON object with:
{
  "summary": "<2-3 sentence executive summary of team activity>",
  "active_areas": ["<area>", ...],
  "recent_issues": [{"key": "<JIRA-123>", "title": "...", "status": "..."}],
  "recent_commits": [{"sha": "<short sha>", "message": "...", "repo": "..."}],
  "blockers": ["<blocker if evident from tickets>"],
  "generated_at": "<ISO datetime>"
}

Be concise. Do not hallucinate. Use only the data provided."""


@celery_app.task(name="ingestion.jobs.cag_job.run_cag")
def run_cag() -> dict[str, Any]:
    return asyncio.run(_run_cag_async())


async def _run_cag_async() -> dict[str, Any]:
    from ingestion.storage.supabase_store import get_all_teams, get_client, update_cag_snapshot

    sb = get_client()
    teams = get_all_teams(client=sb)
    logger.info("cag_job: processing %d teams", len(teams))

    results: dict[str, str] = {}
    for team in teams:
        team_id = team["team_id"]
        try:
            snapshot = await _build_team_snapshot(team_id, sb)
            update_cag_snapshot(team_id, snapshot, client=sb)
            results[team_id] = "ok"
        except Exception:
            logger.exception("cag_job: failed to build snapshot for team %s", team_id)
            results[team_id] = "error"

        # Refresh the routing manifest gists alongside the nightly snapshot.
        # Independent of the snapshot result — a manifest failure must not mask it.
        try:
            await _refresh_team_manifest(team_id, sb)
        except Exception:
            logger.exception("cag_job: failed to refresh routing manifest for team %s", team_id)

    return results


async def _refresh_team_manifest(team_id: str, sb: Any) -> None:
    """Rebuild the manifest structure and (re)generate per-entity gists via the LLM."""
    from ingestion.storage.manifest_store import build_manifest_structure, update_routing_manifest

    manifest = await asyncio.to_thread(build_manifest_structure, team_id, sb)

    titles = await asyncio.to_thread(_fetch_entity_titles, team_id, sb)
    if titles:
        try:
            gists = await _generate_gists(titles)
            _apply_gists(manifest, gists)
        except Exception:
            logger.exception("cag_job: gist generation failed for team %s — storing structure only", team_id)

    await asyncio.to_thread(update_routing_manifest, team_id, manifest, sb)
    logger.info("cag_job: refreshed routing manifest for team %s", team_id)


def _fetch_entity_titles(team_id: str, sb: Any) -> dict[str, dict[str, list[str]]]:
    """Collect up to a handful of document titles per space/repo/project for gisting."""
    from ingestion.storage.manifest_store import _jira_project

    out: dict[str, dict[str, list[str]]] = {"confluence": {}, "github": {}, "jira": {}}
    try:
        result = (
            sb.table("documents")
            .select("source_type, metadata, title")
            .eq("team_id", team_id)
            .execute()
        )
        docs = result.data or []
    except Exception:
        logger.exception("cag_job: failed to fetch titles for team %s", team_id)
        return out

    def _add(bucket: dict[str, list[str]], key: str, title: str) -> None:
        lst = bucket.setdefault(key, [])
        if title and len(lst) < 8:
            lst.append(title)

    for doc in docs:
        stype = doc.get("source_type")
        meta = doc.get("metadata") or {}
        title = doc.get("title") or ""
        if stype == "confluence":
            _add(out["confluence"], meta.get("space_key") or "unknown", title)
        elif stype == "github":
            _add(out["github"], meta.get("repo") or "unknown", title)
        elif stype == "jira":
            _add(out["jira"], _jira_project(meta), title)

    return out


_GIST_SYSTEM_PROMPT = """You label knowledge sources for a retrieval router.

Given document titles grouped by source (Confluence spaces, GitHub repos, Jira
projects), write a single concise gist (max 15 words) describing what each source
contains. The gist helps a router decide whether a user query belongs to that
source. Be specific and factual; do not invent topics not implied by the titles.

Return ONLY valid JSON, no markdown fences, matching the input grouping:
{
  "confluence": {"<space_key>": "<gist>"},
  "github": {"<repo>": "<gist>"},
  "jira": {"<project>": "<gist>"}
}"""


async def _generate_gists(titles: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, str]]:
    import json

    payload = json.dumps(titles, ensure_ascii=False)
    raw = await _call_gemini_with_system(_GIST_SYSTEM_PROMPT, payload)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned else cleaned
        cleaned = cleaned.replace("json", "", 1).strip() if cleaned.lstrip().startswith("json") else cleaned
    return json.loads(cleaned)


def _apply_gists(manifest: dict[str, Any], gists: dict[str, dict[str, str]]) -> None:
    for space, gist in (gists.get("confluence") or {}).items():
        entry = manifest["confluence"]["spaces"].get(space)
        if entry:
            entry["gist"] = gist
    for repo, gist in (gists.get("github") or {}).items():
        entry = manifest["github"]["repos"].get(repo)
        if entry:
            entry["gist"] = gist
    for proj, gist in (gists.get("jira") or {}).items():
        entry = manifest["jira"]["projects"].get(proj)
        if entry:
            entry["gist"] = gist


async def _build_team_snapshot(team_id: str, sb: Any) -> str:
    from ingestion.config import settings

    since = datetime.utcnow() - timedelta(days=settings.cag_lookback_days)
    since_str = since.strftime("%Y-%m-%d")

    jira_text = await _fetch_jira_activity(since_str)
    github_text = await _fetch_github_activity(team_id, sb, since_str)

    combined = f"Jira activity (last {settings.cag_lookback_days} days):\n{jira_text}\n\nGitHub commits (last {settings.cag_lookback_days} days):\n{github_text}"

    # Truncate to stay under token budget; rough estimate is 4 chars/token
    max_chars = settings.cag_max_tokens * 4
    if len(combined) > max_chars:
        combined = combined[:max_chars]
        logger.warning("cag_job: truncated input for team %s to ~%d tokens", team_id, settings.cag_max_tokens)

    snapshot = await _call_gemini(combined)
    return snapshot


async def _fetch_jira_activity(since: str) -> str:
    from ingestion.config import settings

    if not settings.jira_base_url or not settings.jira_api_token:
        return "(Jira not configured)"

    import base64
    import httpx

    jql = f'project = "{settings.jira_project_key}" AND updated >= "{since}" ORDER BY updated DESC'
    url = f"{settings.jira_base_url}/rest/api/3/search"
    credentials = base64.b64encode(
        f"{settings.confluence_email}:{settings.jira_api_token}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {credentials}", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            resp = await client.get(url, params={"jql": jql, "maxResults": 50, "fields": "summary,status,assignee,updated"})
            resp.raise_for_status()
            issues = resp.json().get("issues", [])

        lines = []
        for issue in issues:
            f = issue["fields"]
            status = f.get("status", {}).get("name", "?")
            assignee = (f.get("assignee") or {}).get("displayName", "unassigned")
            lines.append(f"- [{issue['key']}] {f.get('summary', '')} | {status} | {assignee}")
        return "\n".join(lines) if lines else "(no recent Jira activity)"
    except Exception:
        logger.exception("cag_job: Jira fetch failed")
        return "(Jira fetch failed)"


async def _fetch_github_activity(team_id: str, sb: Any, since: str) -> str:
    from ingestion.config import settings

    if not settings.github_token:
        return "(GitHub not configured)"

    import httpx

    try:
        result = (
            sb.table("documents")
            .select("source_url, metadata")
            .eq("team_id", team_id)
            .eq("source_type", "github")
            .execute()
        )
        repos = result.data or []
    except Exception:
        logger.exception("cag_job: failed to fetch repos for team %s", team_id)
        return "(GitHub repo lookup failed)"

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    lines: list[str] = []
    async with httpx.AsyncClient(headers=headers, timeout=20) as client:
        seen_repos: set[str] = set()
        for doc in repos:
            meta = doc.get("metadata") or {}
            repo = meta.get("repo")
            if not repo or repo in seen_repos:
                continue
            seen_repos.add(repo)

            url = f"{settings.github_api_url}/repos/{repo}/commits"
            try:
                resp = await client.get(url, params={"since": f"{since}T00:00:00Z", "per_page": 20})
                resp.raise_for_status()
                for commit in resp.json():
                    sha = commit["sha"][:7]
                    message = commit["commit"]["message"].split("\n")[0]
                    lines.append(f"- [{repo}] {sha} {message}")
            except Exception:
                logger.exception("cag_job: commit fetch failed for %s", repo)

    return "\n".join(lines) if lines else "(no recent GitHub activity)"


async def _call_gemini(user_message: str) -> str:
    return await _call_gemini_with_system(_CAG_SYSTEM_PROMPT, user_message)


async def _call_gemini_with_system(system_prompt: str, user_message: str) -> str:
    import asyncio

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    from ingestion.config import settings

    llm = ChatGoogleGenerativeAI(
        model=settings.cag_model,
        google_api_key=settings.google_api_key,
        temperature=0.0,
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

    for attempt in range(3):
        try:
            response = await llm.ainvoke(messages)
            return response.content
        except Exception as exc:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError("Unreachable")
