from __future__ import annotations

import logging

from ingestion.config import settings
from ingestion.models import RawDocument
from ingestion.sources.base import BaseSource

logger = logging.getLogger(__name__)


class JiraSource(BaseSource):
    def __init__(
        self,
        team_id: str,
        project_key: str = "",
        lookback_days: int = 30,
        base_url: str = "",
        api_token: str = "",
    ) -> None:
        self._team_id = team_id
        self._project_key = project_key or settings.jira_project_key
        self._lookback_days = lookback_days
        self._base_url = base_url or settings.jira_base_url
        self._api_token = api_token or settings.jira_api_token

    def source_type(self) -> str:
        return "jira"

    async def fetch(self) -> list[RawDocument]:
        """Stub — returns empty until JIRA_BASE_URL and JIRA_API_TOKEN are configured."""
        if not self._base_url or not self._api_token:
            logger.info("jira: credentials not configured, returning empty")
            return []

        logger.warning("jira: fetch stub returning empty results")
        return []

        # Real implementation shape (uncomment when credentials available):
        #
        # since = (datetime.utcnow() - timedelta(days=self._lookback_days)).strftime("%Y-%m-%d")
        # jql = f'project = "{self._project_key}" AND updated >= "{since}" ORDER BY updated DESC'
        # url = f"{self._base_url}/rest/api/3/search"
        # import base64
        # headers = {
        #     "Authorization": "Basic " + base64.b64encode(
        #         f"{settings.confluence_email}:{self._api_token}".encode()
        #     ).decode(),
        #     "Accept": "application/json",
        # }
        # async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        #     resp = await client.get(url, params={"jql": jql, "maxResults": 100, "fields": "summary,description,status,assignee,updated"})
        #     resp.raise_for_status()
        #     issues = resp.json().get("issues", [])
        # docs = []
        # for issue in issues:
        #     f = issue["fields"]
        #     text = f"{f.get('summary', '')}\n{f.get('description') or ''}"
        #     doc_id = hashlib.sha256(f"jira:{issue['key']}".encode()).hexdigest()
        #     docs.append(RawDocument(
        #         doc_id=doc_id,
        #         title=f"{issue['key']}: {f.get('summary', '')}",
        #         content=text,
        #         source_url=f"{self._base_url}/browse/{issue['key']}",
        #         source_type="jira",
        #         team_id=self._team_id,
        #         metadata={"issue_key": issue["key"], "status": f.get("status", {}).get("name")},
        #     ))
        # return docs
