from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from supabase import Client

from ingestion.config import settings
from ingestion.models import RawDocument
from ingestion.sources.base import BaseSource

logger = logging.getLogger(__name__)


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    path = urlparse(repo_url).path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {repo_url}")
    return parts[0], parts[1]


class GithubSource(BaseSource):
    def __init__(
        self,
        team_id: str,
        repo_url: str,
        supabase_client: Client,
        path_filter: str = "",
        branch: str = "",
        token: str = "",
    ) -> None:
        self._team_id = team_id
        self._repo_url = repo_url
        self._supabase = supabase_client
        self._path_filter = path_filter or settings.github_path_filter
        self._branch = branch or settings.github_branch
        self._token = token or settings.github_token
        self._owner, self._repo = _parse_owner_repo(repo_url)

    def source_type(self) -> str:
        return "github"

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def fetch(self) -> list[RawDocument]:
        async with httpx.AsyncClient(headers=self._headers(), timeout=30) as client:
            latest_sha = await self._get_latest_commit_sha(client)
            stored_sha = self._get_stored_sha()

            if latest_sha and latest_sha == stored_sha:
                logger.info("github: %s/%s unchanged at SHA %s — skipping", self._owner, self._repo, latest_sha)
                return []

            docs = await self._fetch_markdown_files(client, latest_sha or self._branch)

            if docs and latest_sha:
                self._store_sha(latest_sha)

            logger.info("github: fetched %d documents from %s/%s", len(docs), self._owner, self._repo)
            return docs

    async def _get_latest_commit_sha(self, client: httpx.AsyncClient) -> Optional[str]:
        url = f"{settings.github_api_url}/repos/{self._owner}/{self._repo}/commits"
        params = {"path": self._path_filter, "per_page": 1, "sha": self._branch}
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            commits = resp.json()
            return commits[0]["sha"] if commits else None
        except Exception:
            logger.exception("github: failed to get latest commit SHA")
            return None

    def _get_stored_sha(self) -> Optional[str]:
        repo_doc_id = self._repo_doc_id()
        try:
            result = (
                self._supabase.table("documents")
                .select("last_commit_sha")
                .eq("doc_id", repo_doc_id)
                .maybe_single()
                .execute()
            )
            return result.data["last_commit_sha"] if result.data else None
        except Exception:
            logger.exception("github: failed to fetch stored SHA")
            return None

    def _store_sha(self, sha: str) -> None:
        repo_doc_id = self._repo_doc_id()
        try:
            self._supabase.table("documents").upsert(
                {
                    "doc_id": repo_doc_id,
                    "title": f"{self._owner}/{self._repo}",
                    "source_url": self._repo_url,
                    "source_type": "github",
                    "team_id": self._team_id,
                    "last_commit_sha": sha,
                },
                on_conflict="doc_id",
            ).execute()
        except Exception:
            logger.exception("github: failed to store new SHA")

    def _repo_doc_id(self) -> str:
        return hashlib.sha256(f"github:repo:{self._owner}/{self._repo}".encode()).hexdigest()

    async def _fetch_markdown_files(self, client: httpx.AsyncClient, ref: str) -> list[RawDocument]:
        url = f"{settings.github_api_url}/repos/{self._owner}/{self._repo}/git/trees/{ref}"
        try:
            resp = await client.get(url, params={"recursive": "1"})
            resp.raise_for_status()
            tree = resp.json().get("tree", [])
        except Exception:
            logger.exception("github: failed to fetch file tree")
            return []

        md_paths = [
            item["path"]
            for item in tree
            if item["type"] == "blob"
            and item["path"].endswith(".md")
            and item["path"].startswith(self._path_filter)
        ]

        docs: list[RawDocument] = []
        for path in md_paths:
            doc = await self._fetch_file(client, path)
            if doc:
                docs.append(doc)
        return docs

    async def _fetch_file(self, client: httpx.AsyncClient, path: str) -> Optional[RawDocument]:
        url = f"{settings.github_api_url}/repos/{self._owner}/{self._repo}/contents/{path}"
        try:
            resp = await client.get(url, params={"ref": self._branch})
            resp.raise_for_status()
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            doc_id = hashlib.sha256(f"github:{self._owner}/{self._repo}/{path}".encode()).hexdigest()
            source_url = data.get("html_url", f"{self._repo_url}/blob/{self._branch}/{path}")
            return RawDocument(
                doc_id=doc_id,
                title=path.split("/")[-1].removesuffix(".md"),
                content=content,
                source_url=source_url,
                source_type="github",
                team_id=self._team_id,
                metadata={"repo": f"{self._owner}/{self._repo}", "path": path, "branch": self._branch},
            )
        except Exception:
            logger.exception("github: failed to fetch file %s", path)
            return None
