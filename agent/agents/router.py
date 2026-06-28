"""Deterministic query router — Stage 0 of route-then-retrieve.

Runs BEFORE the LLM planner. Uses cheap, deterministic signals (ticket-id
regex, source keywords) plus a per-team knowledge manifest to decide which
sources a query belongs to. It emits a `RoutingDecision`:

- `scope`: a narrowing Qdrant pre-filter — populated ONLY when confidence is
  "high" (soft-routing policy). When unsure, `scope=None` so retrieval stays
  broad and a correct answer can never become unreachable.
- `suggested_agents`: a hint the planner is told to prefer (it may still add
  others). This is what prunes fan-out and saves cost.

The router never calls an LLM — that work is left to the planner, which is what
it is designed for. The router just filters the easy/obvious cases first.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from agent.models import QueryInput, RetrievalScope, RoutingDecision

logger = logging.getLogger(__name__)

# Kept in sync with ingestion/storage/manifest_store.MANIFEST_CACHE_KEY.
MANIFEST_CACHE_KEY = "gs:manifest:{team_id}"
MANIFEST_TTL_SECONDS = 600

# Jira-style ticket id, e.g. KAN-7, PROJ-1234. Anchored on word boundaries.
_TICKET_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

_AGGREGATE_KEYWORDS = (
    "how many", "how much", "number of", "count of", "list all",
    "statistics", "stats", "failed job", "ingestion status", "ingest status",
)
_CONFLUENCE_KEYWORDS = ("confluence", "wiki", "design doc", "meeting note", "runbook page")
_SLACK_KEYWORDS = ("slack", "discussed", "conversation", "what was said")
_JIRA_KEYWORDS = ("jira", "ticket", "sprint", "backlog", "bug report")

# Minimum token length for matching a manifest entity name, to avoid false
# positives on common short words (e.g. "api", "web").
_MIN_ENTITY_TOKEN_LEN = 4


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _load_manifest_supabase(team_id: str) -> Optional[dict[str, Any]]:
    # Lazy import: only hit Supabase on a Redis cache miss.
    from ingestion.storage.manifest_store import get_routing_manifest
    return get_routing_manifest(team_id)


async def _load_manifest(team_id: str) -> Optional[dict[str, Any]]:
    """Redis-first read of the team manifest, falling back to Supabase."""
    key = MANIFEST_CACHE_KEY.format(team_id=team_id)

    try:
        from src.utils.clients import get_redis
        redis = await get_redis()
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        logger.debug("router: manifest cache read failed for team %s", team_id, exc_info=True)
        redis = None

    manifest: Optional[dict[str, Any]] = None
    try:
        manifest = await asyncio.to_thread(_load_manifest_supabase, team_id)
    except Exception:
        logger.warning("router: manifest Supabase read failed for team %s", team_id)

    if manifest is not None:
        try:
            from src.utils.clients import get_redis
            redis = await get_redis()
            await redis.set(key, json.dumps(manifest), ex=MANIFEST_TTL_SECONDS)
        except Exception:
            logger.debug("router: manifest cache write failed for team %s", team_id, exc_info=True)

    return manifest


def _match_manifest_entities(
    tokens: set[str],
    manifest: dict[str, Any],
    space_keys: set[str],
    repos: set[str],
    jira_projects: set[str],
    source_types: set[str],
    reasons: list[str],
) -> bool:
    """Match query tokens against known spaces/repos/projects. Returns True if any hit."""
    hit = False

    for space in (manifest.get("confluence", {}).get("spaces", {}) or {}):
        if space and space.lower() in tokens and len(space) >= 3:
            space_keys.add(space)
            source_types.add("confluence")
            reasons.append(f"matched Confluence space '{space}'")
            hit = True

    for repo in (manifest.get("github", {}).get("repos", {}) or {}):
        if not repo:
            continue
        name = repo.split("/")[-1].lower()
        if (repo.lower() in tokens or name in tokens) and len(name) >= _MIN_ENTITY_TOKEN_LEN:
            repos.add(repo)
            reasons.append(f"matched GitHub repo '{repo}'")
            hit = True

    for proj in (manifest.get("jira", {}).get("projects", {}) or {}):
        if proj and proj.lower() in tokens and len(proj) >= 2:
            jira_projects.add(proj)
            source_types.add("jira")
            reasons.append(f"matched Jira project '{proj}'")
            hit = True

    return hit


async def run_router(query_input: QueryInput) -> RoutingDecision:
    query = query_input.query
    ql = query.lower()
    tokens = _tokens(query)

    source_types: set[str] = set()
    space_keys: set[str] = set()
    repos: set[str] = set()
    jira_projects: set[str] = set()
    suggested: set[str] = set()
    reasons: list[str] = []

    entity_hit = False

    # 1. Ticket ids are an unambiguous Jira signal.
    ticket_ids = _TICKET_ID_RE.findall(query)
    if ticket_ids:
        suggested.add("ticket_lookup")
        source_types.add("jira")
        for tid in ticket_ids:
            jira_projects.add(tid.split("-", 1)[0])
        entity_hit = True
        reasons.append(f"ticket id(s) {ticket_ids}")

    # 2. Aggregate / structured intent -> SQL.
    if any(k in ql for k in _AGGREGATE_KEYWORDS):
        suggested.add("sql_query")
        reasons.append("aggregate/structured intent")

    # 3. Explicit source keywords (weaker signal — no specific entity).
    if any(k in ql for k in _CONFLUENCE_KEYWORDS):
        suggested.add("confluence_search")
        source_types.add("confluence")
        reasons.append("Confluence keyword")
    if any(k in ql for k in _SLACK_KEYWORDS):
        suggested.add("slack_search")
        reasons.append("Slack keyword")
    if any(k in ql for k in _JIRA_KEYWORDS):
        suggested.add("ticket_lookup")
        source_types.add("jira")
        reasons.append("Jira keyword")

    # 4. Strongest signal: query names a known space/repo/project in the manifest.
    manifest = await _load_manifest(query_input.team_id)
    if manifest:
        if _match_manifest_entities(
            tokens, manifest, space_keys, repos, jira_projects, source_types, reasons
        ):
            entity_hit = True
            if space_keys:
                suggested.add("confluence_search")

    # Confidence: a specific entity (ticket id / space / repo / project) => high;
    # a bare source keyword => medium; nothing => low.
    if entity_hit:
        confidence = "high"
    elif suggested:
        confidence = "medium"
    else:
        confidence = "low"

    # Soft fallback: keep doc_search in play whenever we are not highly confident,
    # so a broad path always exists.
    if confidence != "high" or not suggested:
        suggested.add("doc_search")

    # Soft-routing policy: only emit a narrowing scope at high confidence.
    scope: Optional[RetrievalScope] = None
    if confidence == "high":
        candidate = RetrievalScope(
            source_types=sorted(source_types),
            space_keys=sorted(space_keys),
            repos=sorted(repos),
            jira_projects=sorted(jira_projects),
        )
        if not candidate.is_empty():
            scope = candidate

    decision = RoutingDecision(
        scope=scope,
        suggested_agents=sorted(suggested),
        confidence=confidence,
        reasoning="; ".join(reasons) if reasons else "no strong routing signal — broad search",
    )
    logger.info(
        "router: confidence=%s agents=%s scope=%s",
        confidence, decision.suggested_agents, scope.model_dump() if scope else None,
    )
    return decision


def manifest_digest(manifest: Optional[dict[str, Any]]) -> str:
    """Compact one-paragraph summary of the manifest for the planner prompt."""
    if not manifest:
        return "No knowledge manifest available for this team yet."

    parts: list[str] = []
    spaces = manifest.get("confluence", {}).get("spaces", {}) or {}
    if spaces:
        items = [f"{k} ({v.get('gist') or v.get('doc_count', 0)})" for k, v in spaces.items()]
        parts.append("Confluence spaces: " + "; ".join(items))
    repos = manifest.get("github", {}).get("repos", {}) or {}
    if repos:
        items = [f"{k} ({v.get('gist') or v.get('doc_count', 0)})" for k, v in repos.items()]
        parts.append("GitHub repos: " + "; ".join(items))
    projects = manifest.get("jira", {}).get("projects", {}) or {}
    if projects:
        items = [f"{k} ({v.get('gist') or v.get('doc_count', 0)})" for k, v in projects.items()]
        parts.append("Jira projects: " + "; ".join(items))

    return "\n".join(parts) if parts else "Knowledge manifest is empty."
