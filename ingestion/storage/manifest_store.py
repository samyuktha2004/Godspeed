"""Routing manifest store — the per-team "what exists and where" index.

The manifest is a compact map of a team's knowledge sources (Confluence spaces,
GitHub repos, Jira projects, file/pdf groups) with document counts and optional
one-line LLM gists. It is read at query time by the deterministic router
(`agent/agents/router.py`) to narrow retrieval scope — cheaper and more precise
than fanning out across every source.

Two-speed freshness:
- **structure** (counts + which spaces/repos/projects exist) is recomputed from
  the `documents` table on every ingest — cheap, no LLM, no re-embedding.
- **gists** (a sentence describing each space/repo) are regenerated nightly by
  the CAG job (`ingestion/jobs/cag_job.py`).

Source of truth is Supabase `teams.routing_manifest`; the agent caches it in
Redis. Writers here best-effort bust that cache so updates show promptly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from ingestion.config import settings
from ingestion.storage.supabase_store import get_client

logger = logging.getLogger(__name__)

# Redis key the agent-side router reads from. Kept in sync with agent/agents/router.py.
MANIFEST_CACHE_KEY = "gs:manifest:{team_id}"


def _bust_cache(team_id: str) -> None:
    """Best-effort: drop the cached manifest so the next router read refreshes.

    Uses a short-lived sync Redis connection — never raises into the caller.
    """
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.delete(MANIFEST_CACHE_KEY.format(team_id=team_id))
        client.close()
    except Exception:
        logger.debug("manifest_store: cache bust skipped for team %s", team_id, exc_info=True)


def get_routing_manifest(team_id: str, client: Optional[Any] = None) -> Optional[dict[str, Any]]:
    sb = client or get_client()
    try:
        result = (
            sb.table("teams")
            .select("routing_manifest")
            .eq("team_id", team_id)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return None
        return result.data.get("routing_manifest")
    except Exception:
        logger.exception("manifest_store: failed to read manifest for team %s", team_id)
        return None


def update_routing_manifest(team_id: str, manifest: dict[str, Any], client: Optional[Any] = None) -> None:
    sb = client or get_client()
    try:
        sb.table("teams").upsert(
            {
                "team_id": team_id,
                "routing_manifest": manifest,
                "manifest_at": datetime.utcnow().isoformat(),
            },
            on_conflict="team_id",
        ).execute()
        _bust_cache(team_id)
        logger.info("manifest_store: updated routing manifest for team %s", team_id)
    except Exception:
        logger.exception("manifest_store: failed to update manifest for team %s", team_id)
        raise


def _jira_project(meta: dict[str, Any]) -> str:
    """Derive a Jira project key from document metadata, defensively."""
    proj = meta.get("project") or meta.get("project_key")
    if proj:
        return str(proj)
    issue_key = meta.get("issue_key")
    if isinstance(issue_key, str) and "-" in issue_key:
        return issue_key.split("-", 1)[0]
    return settings.jira_project_key or "unknown"


def build_manifest_structure(team_id: str, client: Optional[Any] = None) -> dict[str, Any]:
    """Recompute the manifest structure (counts + entities) from `documents`.

    Cheap: a team's *document* count is modest and we only read metadata, never
    chunk text or vectors. Gists are NOT produced here.
    """
    sb = client or get_client()
    manifest: dict[str, Any] = {
        "confluence": {"spaces": {}},
        "github": {"repos": {}},
        "jira": {"projects": {}},
        "file": {"doc_count": 0},
        "pdf": {"doc_count": 0},
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        result = (
            sb.table("documents")
            .select("source_type, metadata")
            .eq("team_id", team_id)
            .execute()
        )
        docs = result.data or []
    except Exception:
        logger.exception("manifest_store: failed to fetch documents for team %s", team_id)
        return manifest

    for doc in docs:
        stype = doc.get("source_type") or "unknown"
        meta = doc.get("metadata") or {}

        if stype == "confluence":
            key = meta.get("space_key") or "unknown"
            entry = manifest["confluence"]["spaces"].setdefault(key, {"doc_count": 0, "gist": None})
            entry["doc_count"] += 1
        elif stype == "github":
            repo = meta.get("repo") or "unknown"
            entry = manifest["github"]["repos"].setdefault(repo, {"doc_count": 0, "gist": None, "top_paths": []})
            entry["doc_count"] += 1
            path = meta.get("path")
            if isinstance(path, str) and path:
                top = path.split("/", 1)[0]
                if top and top not in entry["top_paths"] and len(entry["top_paths"]) < 5:
                    entry["top_paths"].append(top)
        elif stype == "jira":
            proj = _jira_project(meta)
            entry = manifest["jira"]["projects"].setdefault(proj, {"doc_count": 0, "gist": None})
            entry["doc_count"] += 1
        elif stype in ("file", "pdf"):
            manifest[stype]["doc_count"] += 1

    return manifest


def _merge_gists(new: dict[str, Any], old: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Carry forward existing gists onto a freshly-built structure."""
    if not old:
        return new
    for space, entry in new["confluence"]["spaces"].items():
        prev = old.get("confluence", {}).get("spaces", {}).get(space)
        if prev and prev.get("gist"):
            entry["gist"] = prev["gist"]
    for repo, entry in new["github"]["repos"].items():
        prev = old.get("github", {}).get("repos", {}).get(repo)
        if prev and prev.get("gist"):
            entry["gist"] = prev["gist"]
    for proj, entry in new["jira"]["projects"].items():
        prev = old.get("jira", {}).get("projects", {}).get(proj)
        if prev and prev.get("gist"):
            entry["gist"] = prev["gist"]
    return new


def refresh_manifest_structure(team_id: str, client: Optional[Any] = None) -> dict[str, Any]:
    """Rebuild structure, preserve any existing gists, and persist. Best-effort.

    Called at the end of every ingest job. Wrapped so a manifest failure never
    breaks ingestion.
    """
    sb = client or get_client()
    new = build_manifest_structure(team_id, client=sb)
    existing = get_routing_manifest(team_id, client=sb)
    merged = _merge_gists(new, existing)
    update_routing_manifest(team_id, merged, client=sb)
    return merged
