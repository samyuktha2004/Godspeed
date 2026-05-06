from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx

from ingestion.models import RawDocument
from src.confluence_agent.config import confluence_config

logger = logging.getLogger(__name__)

_EXPAND = "body.storage,version,ancestors,space"


class ConfluenceAdapter:
    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        email: str = "",
        team_id: str = "",
    ) -> None:
        self._base_url = (base_url or confluence_config.confluence_base_url).rstrip("/")
        self._token = token or confluence_config.confluence_token
        self._email = email or confluence_config.confluence_email
        self._team_id = team_id or confluence_config.team_id

    def _auth_headers(self) -> dict[str, str]:
        credentials = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        return {"Authorization": f"Basic {credentials}", "Accept": "application/json"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._auth_headers(), timeout=30)

    def _page_to_raw_document(self, page: dict) -> Optional[RawDocument]:
        try:
            page_id = page["id"]
            title = page.get("title", "Untitled")
            space_key = (page.get("space") or {}).get("key", "")
            html_body = page.get("body", {}).get("storage", {}).get("value", "")
            ancestors = [a.get("title", "") for a in page.get("ancestors", [])]
            version = (page.get("version") or {}).get("number", 0)

            doc_id = hashlib.sha256(f"confluence:{page_id}".encode()).hexdigest()
            return RawDocument(
                doc_id=doc_id,
                title=title,
                content=html_body,  # raw storage HTML — chunker will parse it
                source_url=f"{self._base_url}/wiki/spaces/{space_key}/pages/{page_id}",
                source_type="confluence",
                team_id=self._team_id,
                metadata={
                    "page_id": page_id,
                    "space_key": space_key,
                    "ancestors": ancestors,
                    "version": version,
                },
            )
        except Exception:
            logger.exception("confluence_adapter: failed to parse page payload")
            return None

    async def fetch_page(self, page_id: str) -> Optional[RawDocument]:
        if not self._base_url or not self._token:
            logger.warning("confluence_adapter: credentials not configured")
            return None
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
        async with self._client() as client:
            try:
                resp = await client.get(url, params={"expand": _EXPAND})
                resp.raise_for_status()
                return self._page_to_raw_document(resp.json())
            except Exception:
                logger.exception("confluence_adapter: failed to fetch page %s", page_id)
                return None

    async def fetch_space(self, space_key: str) -> list[RawDocument]:
        if not self._base_url or not self._token:
            logger.warning("confluence_adapter: credentials not configured")
            return []
        url = f"{self._base_url}/wiki/rest/api/content"
        params: dict = {
            "spaceKey": space_key,
            "expand": _EXPAND,
            "limit": 50,
            "start": 0,
        }
        docs: list[RawDocument] = []
        async with self._client() as client:
            while True:
                try:
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
                except Exception:
                    logger.exception("confluence_adapter: fetch_space failed at start=%d", params["start"])
                    break

        logger.info("confluence_adapter: fetched %d pages from space %s", len(docs), space_key)
        return docs

    async def fetch_incremental(self, space_key: str, since: datetime) -> list[RawDocument]:
        """Return pages modified since `since`. Uses CQL if available, falls back to full fetch."""
        if not self._base_url or not self._token:
            return []
        since_str = since.strftime("%Y-%m-%d %H:%M")
        url = f"{self._base_url}/wiki/rest/api/content/search"
        params = {
            "cql": f'space = "{space_key}" AND lastModified >= "{since_str}"',
            "expand": _EXPAND,
            "limit": 50,
            "start": 0,
        }
        docs: list[RawDocument] = []
        async with self._client() as client:
            while True:
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 404:
                        # CQL not supported — fall back to full space fetch
                        return await self.fetch_space(space_key)
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
                except Exception:
                    logger.exception("confluence_adapter: incremental fetch failed")
                    break

        return docs
