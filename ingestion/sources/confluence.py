from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from ingestion.config import settings
from ingestion.models import RawDocument
from ingestion.sources.base import BaseSource

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s{2,}")


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", text).strip()


class ConfluenceSource(BaseSource):
    def __init__(
        self,
        team_id: str,
        space_key: str,
        page_ids: Optional[list[str]] = None,
        base_url: str = "",
        token: str = "",
        email: str = "",
    ) -> None:
        self._team_id = team_id
        self._space_key = space_key
        self._page_ids = page_ids
        self._base_url = base_url or settings.confluence_base_url
        self._token = token or settings.confluence_token
        self._email = email or settings.confluence_email

    def source_type(self) -> str:
        return "confluence"

    def _auth_headers(self) -> dict[str, str]:
        import base64
        credentials = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        return {"Authorization": f"Basic {credentials}", "Accept": "application/json"}

    async def fetch(self) -> list[RawDocument]:
        if not self._base_url or not self._token:
            logger.warning("confluence: credentials not configured, returning empty")
            return []

        async with httpx.AsyncClient(headers=self._auth_headers(), timeout=30) as client:
            if self._page_ids:
                return await self._fetch_pages(client, self._page_ids)
            return await self._fetch_space(client)

    async def _fetch_space(self, client: httpx.AsyncClient) -> list[RawDocument]:
        docs: list[RawDocument] = []
        url = f"{self._base_url}/wiki/rest/api/content"
        params: dict = {"spaceKey": self._space_key, "expand": "body.storage", "limit": 50, "start": 0}

        while True:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            for page in data.get("results", []):
                doc = self._page_to_raw_document(page)
                if doc:
                    docs.append(doc)
            if data.get("_links", {}).get("next"):
                params["start"] += params["limit"]
            else:
                break

        logger.info("confluence: fetched %d pages from space %s", len(docs), self._space_key)
        return docs

    async def _fetch_pages(self, client: httpx.AsyncClient, page_ids: list[str]) -> list[RawDocument]:
        docs: list[RawDocument] = []
        for page_id in page_ids:
            url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
            try:
                resp = await client.get(url, params={"expand": "body.storage"})
                resp.raise_for_status()
                doc = self._page_to_raw_document(resp.json())
                if doc:
                    docs.append(doc)
            except Exception:
                logger.exception("confluence: failed to fetch page %s", page_id)
        return docs

    def _page_to_raw_document(self, page: dict) -> Optional[RawDocument]:
        try:
            page_id = page["id"]
            title = page.get("title", "Untitled")
            html_body = page.get("body", {}).get("storage", {}).get("value", "")
            content = _strip_html(html_body)
            if not content.strip():
                return None
            source_url = f"{self._base_url}/wiki/spaces/{self._space_key}/pages/{page_id}"
            doc_id = hashlib.sha256(f"confluence:{page_id}".encode()).hexdigest()
            return RawDocument(
                doc_id=doc_id,
                title=title,
                content=content,
                source_url=source_url,
                source_type="confluence",
                team_id=self._team_id,
                metadata={"page_id": page_id, "space_key": self._space_key},
            )
        except Exception:
            logger.exception("confluence: failed to parse page payload")
            return None
