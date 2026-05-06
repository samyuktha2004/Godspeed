"""Web scraper adapter for URL-based content ingestion."""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from docling import DocumentConverter

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    """Normalized document model for all sources."""

    uri: str
    source_type: str
    source_subtype: str
    title: str
    content: str
    content_hash: str
    created_at: datetime
    updated_at: datetime
    author_ids: list[str]
    space_id: str
    parent_ids: list[str] = None
    tags: list[str] = None
    raw_metadata: dict = None
    content_type: str = "text"
    priority: int = 3
    ttl_seconds: Optional[int] = None
    source_config: dict = None

    def __post_init__(self):
        if self.parent_ids is None:
            self.parent_ids = []
        if self.tags is None:
            self.tags = []
        if self.raw_metadata is None:
            self.raw_metadata = {}
        if self.source_config is None:
            self.source_config = {}


class WebScraperAdapter:
    """Adapter for scraping and indexing web content."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=settings.integrations.web_scraper_timeout)
        self.max_content_size = settings.integrations.web_scraper_max_content_size
        self.user_agent = settings.integrations.user_agent

    async def connect(self, credentials: dict) -> None:
        """No authentication needed for public web scraping."""
        pass

    async def fetch_url(self, url: str) -> Optional[RawDocument]:
        """
        Fetch and parse a single URL.

        Args:
            url: URL to scrape

        Returns:
            RawDocument if successful, None otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": self.user_agent}

                async with session.get(
                    url, headers=headers, timeout=self.timeout, ssl=False
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: status {response.status}")
                        return None

                    # Check content size
                    content = await response.read()
                    if len(content) > self.max_content_size:
                        logger.warning(f"Content too large for {url}")
                        return None

                    # Parse content
                    doc = await self._parse_content(
                        url, content, response.headers.get("content-type", "text/html")
                    )
                    return doc

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """Fetch all URLs in a space (not typically used for web scraping)."""
        return []

    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """Fetch only changed pages (requires sitemap or incremental tracking)."""
        return []

    async def fetch_by_query(self, query: str) -> list[RawDocument]:
        """Search for URLs containing keywords (via stored URLs)."""
        return []

    async def _parse_content(
        self, url: str, content: bytes, content_type: str
    ) -> RawDocument:
        """Parse HTML/PDF content and extract text."""

        # Detect file type
        if "application/pdf" in content_type:
            text = await self._extract_pdf_text(content)
            doc_type = "pdf"
        else:
            text = self._extract_html_text(content)
            doc_type = "webpage"

        # Extract title
        soup = BeautifulSoup(content, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else urlparse(url).netloc

        # Generate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Build RawDocument
        doc = RawDocument(
            uri=f"web://{hashlib.sha256(url.encode()).hexdigest()}",
            source_type="web",
            source_subtype=doc_type,
            title=title,
            content=text,
            content_hash=content_hash,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            author_ids=["scraper"],
            space_id="web_content",
            tags=["scraped", doc_type],
            priority=2,
            ttl_seconds=None,
            raw_metadata={"url": url, "domain": urlparse(url).netloc},
        )

        return doc

    def _extract_html_text(self, content: bytes) -> str:
        """Extract text from HTML."""
        soup = BeautifulSoup(content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text

    async def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text from PDF using docling."""
        try:
            converter = DocumentConverter()
            # Save to temp file for docling
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(content)
                temp_path = f.name

            # Parse PDF
            doc_result = converter.convert(temp_path)
            text = doc_result.document.export_to_markdown()

            # Cleanup
            import os
            os.remove(temp_path)

            return text
        except Exception as e:
            logger.warning(f"Failed to extract PDF text: {e}")
            return "[PDF content could not be extracted]"


class SitemapAdapter(WebScraperAdapter):
    """Adapter for scraping sitemap.xml and crawling all URLs."""

    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """
        Fetch all URLs from sitemap.

        Args:
            space_id: Base domain (e.g., "https://example.com")

        Returns:
            List of RawDocuments from all URLs in sitemap
        """
        sitemap_url = f"{space_id.rstrip('/')}/sitemap.xml"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=self.timeout) as response:
                    if response.status != 200:
                        logger.warning(f"Sitemap not found at {sitemap_url}")
                        return []

                    sitemap_content = await response.text()

            # Parse sitemap URLs
            soup = BeautifulSoup(sitemap_content, "xml")
            urls = [loc.text for loc in soup.find_all("loc")]

            # Fetch each URL
            docs = []
            for url in urls:
                try:
                    doc = await self.fetch_url(url)
                    if doc:
                        docs.append(doc)
                except Exception as e:
                    logger.error(f"Error fetching {url}: {e}")
                    continue

                # Rate limiting
                await asyncio.sleep(0.1)

            return docs

        except Exception as e:
            logger.error(f"Error fetching sitemap: {e}")
            return []


class UrlListAdapter(WebScraperAdapter):
    """Adapter for scraping a predefined list of URLs."""

    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """
        Fetch all URLs from a list (passed as space_id).

        Args:
            space_id: JSON-encoded list of URLs

        Returns:
            List of RawDocuments from all URLs
        """
        import json

        try:
            urls = json.loads(space_id)
        except json.JSONDecodeError:
            logger.error(f"Invalid URL list: {space_id}")
            return []

        docs = []
        for url in urls:
            try:
                doc = await self.fetch_url(url)
                if doc:
                    docs.append(doc)
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                continue

            # Rate limiting
            await asyncio.sleep(0.1)

        return docs
