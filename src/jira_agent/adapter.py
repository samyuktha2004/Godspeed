from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from ingestion.models import RawDocument
from src.jira_agent.config import jira_config

logger = logging.getLogger(__name__)

_ISSUE_FIELDS = "summary,description,status,assignee,priority,labels,comment,created,updated,issuetype"


class JiraAdapter:
    def __init__(
        self,
        base_url: str = "",
        email: str = "",
        api_token: str = "",
        team_id: str = "",
    ) -> None:
        self._base_url = (base_url or jira_config.jira_base_url).rstrip("/")
        self._email = email or jira_config.jira_email
        self._api_token = api_token or jira_config.jira_api_token
        self._team_id = team_id or jira_config.team_id

    def _auth_headers(self) -> dict[str, str]:
        credentials = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        return {"Authorization": f"Basic {credentials}", "Accept": "application/json"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._auth_headers(), timeout=30)

    def _issue_to_raw_document(self, issue: dict[str, Any]) -> RawDocument:
        key = issue["key"]
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        description = fields.get("description") or ""
        if isinstance(description, dict):
            # Atlassian Document Format — extract plain text
            description = _extract_adf_text(description)
        status = (fields.get("status") or {}).get("name", "Unknown")
        priority = (fields.get("priority") or {}).get("name", "None")
        assignee_obj = fields.get("assignee") or {}
        assignee = assignee_obj.get("displayName", "Unassigned")
        issue_type = (fields.get("issuetype") or {}).get("name", "Issue")
        labels = ", ".join(fields.get("labels") or [])
        updated = fields.get("updated", "")

        content = (
            f"Issue {key}: {summary}\n"
            f"Type: {issue_type} | Status: {status} | Priority: {priority}\n"
            f"Assignee: {assignee}\n"
            f"Labels: {labels}\n\n"
            f"{description}"
        ).strip()

        doc_id = hashlib.sha256(f"jira:{key}".encode()).hexdigest()
        comments_raw = (fields.get("comment") or {}).get("comments", [])
        comments = [
            {
                "author": (c.get("author") or {}).get("displayName", "Unknown"),
                "body": _extract_adf_text(c["body"]) if isinstance(c.get("body"), dict) else (c.get("body") or ""),
                "created": c.get("created", ""),
            }
            for c in comments_raw
        ]

        return RawDocument(
            doc_id=doc_id,
            title=f"{key}: {summary}",
            content=content,
            source_url=f"{self._base_url}/browse/{key}",
            source_type="jira",
            team_id=self._team_id,
            metadata={
                "issue_key": key,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "issue_type": issue_type,
                "labels": labels,
                "updated": updated,
                "comments": comments,
            },
        )

    async def fetch_issue(self, issue_key: str) -> Optional[RawDocument]:
        if not self._base_url or not self._api_token:
            logger.warning("jira_adapter: credentials not configured")
            return None
        url = f"{self._base_url}/rest/api/3/issue/{issue_key}"
        async with self._client() as client:
            try:
                resp = await client.get(url, params={"fields": _ISSUE_FIELDS})
                resp.raise_for_status()
                return self._issue_to_raw_document(resp.json())
            except Exception:
                logger.exception("jira_adapter: failed to fetch issue %s", issue_key)
                return None

    async def fetch_all(self, project_key: str) -> list[RawDocument]:
        return await self._jql_fetch(f'project = "{project_key}" ORDER BY created ASC')

    async def fetch_incremental(self, project_key: str, since: datetime) -> list[RawDocument]:
        since_str = since.strftime("%Y-%m-%d %H:%M")
        jql = f'project = "{project_key}" AND updated >= "{since_str}" ORDER BY updated ASC'
        return await self._jql_fetch(jql)

    async def _jql_fetch(self, jql: str) -> list[RawDocument]:
        if not self._base_url or not self._api_token:
            logger.warning("jira_adapter: credentials not configured, returning empty")
            return []
        url = f"{self._base_url}/rest/api/3/search"
        start = 0
        page_size = 50
        docs: list[RawDocument] = []

        async with self._client() as client:
            while True:
                try:
                    resp = await client.get(
                        url,
                        params={
                            "jql": jql,
                            "startAt": start,
                            "maxResults": page_size,
                            "fields": _ISSUE_FIELDS,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    issues = data.get("issues", [])
                    for issue in issues:
                        docs.append(self._issue_to_raw_document(issue))
                    total = data.get("total", 0)
                    start += len(issues)
                    if start >= total or not issues:
                        break
                except Exception:
                    logger.exception("jira_adapter: JQL fetch failed at start=%d", start)
                    break

        logger.info("jira_adapter: fetched %d issues via JQL", len(docs))
        return docs


def _extract_adf_text(node: Any) -> str:
    """Recursively extract plain text from Atlassian Document Format JSON."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = []
        for child in node.get("content", []):
            parts.append(_extract_adf_text(child))
        return " ".join(p for p in parts if p).strip()
    if isinstance(node, list):
        return " ".join(_extract_adf_text(item) for item in node).strip()
    return ""
