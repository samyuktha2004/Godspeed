"""Ingestion orchestrator for routing documents through adapters and pipelines."""

import logging
from datetime import datetime
from dataclasses import dataclass

from src.adapters.base import get_adapter_registry
from src.redis.cache import SyncStateCache, RedisCache
from src.redis.locks import DistributedLock
from src.adapters.web_scraper import RawDocument
import redis

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    source_type: str
    space_id: str
    docs_processed: int
    docs_successful: int
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class IngestionOrchestrator:
    """Routes documents through adapters and pipelines."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.sync_state = SyncStateCache(redis_client)
        self.cache = RedisCache(redis_client)
        self.registry = get_adapter_registry()

    async def ingest_from_source(
        self,
        source_type: str,
        space_id: str,
        credentials: dict,
        mode: str = "incremental",
    ) -> IngestResult:
        """
        Orchestrate ingestion from a data source.

        Args:
            source_type: Type of source (e.g., "slack", "github", "web")
            space_id: Identifier within the source (e.g., workspace, org, domain)
            credentials: Auth credentials for the source
            mode: "full" for complete re-crawl, "incremental" for changes only

        Returns:
            IngestResult with statistics
        """
        adapter = self.registry.get(source_type)
        if not adapter:
            logger.error(f"No adapter found for source type: {source_type}")
            return IngestResult(
                source_type=source_type,
                space_id=space_id,
                docs_processed=0,
                docs_successful=0,
                errors=[f"No adapter for {source_type}"],
            )

        # Acquire lock to prevent concurrent syncing
        lock_resource = f"{source_type}:{space_id}"
        lock = DistributedLock(self.redis)

        try:
            acquired = await lock.acquire(lock_resource, timeout_seconds=3600)
            if not acquired:
                logger.warning(f"Could not acquire lock for {lock_resource}, skipping")
                return IngestResult(
                    source_type=source_type,
                    space_id=space_id,
                    docs_processed=0,
                    docs_successful=0,
                    errors=["Lock not acquired"],
                )

            # Connect to source
            try:
                await adapter.connect(credentials)
            except Exception as e:
                logger.error(f"Failed to connect to {source_type}: {e}")
                return IngestResult(
                    source_type=source_type,
                    space_id=space_id,
                    docs_processed=0,
                    docs_successful=0,
                    errors=[str(e)],
                )

            # Fetch documents
            if mode == "full":
                docs = await adapter.fetch_all(space_id)
            else:
                last_sync = await self.sync_state.get_last_sync(source_type, space_id)
                if not last_sync:
                    logger.info(
                        f"No previous sync found for {source_type}:{space_id}, doing full crawl"
                    )
                    docs = await adapter.fetch_all(space_id)
                else:
                    docs = await adapter.fetch_incremental(space_id, last_sync)

            logger.info(f"Fetched {len(docs)} documents from {source_type}:{space_id}")

            # Process documents through pipeline
            results = []
            for doc in docs:
                try:
                    # For now, just cache the document
                    # In production, this would feed into the full ingestion pipeline
                    await self._process_document(doc)
                    results.append(doc)
                except Exception as e:
                    logger.error(f"Failed to process document {doc.uri}: {e}")

            # Update sync timestamp
            await self.sync_state.set_last_sync(source_type, space_id)

            return IngestResult(
                source_type=source_type,
                space_id=space_id,
                docs_processed=len(docs),
                docs_successful=len(results),
                errors=[],
            )

        finally:
            # Release lock
            try:
                await lock.release(lock_resource)
            except Exception as e:
                logger.warning(f"Failed to release lock: {e}")

    async def _process_document(self, doc: RawDocument):
        """Process a document through the ingestion pipeline."""
        # Placeholder: would run through the full pipeline
        # 1. Parsing (Docling)
        # 2. PII masking (GLiNER)
        # 3. Chunking (semantic)
        # 4. Embedding (BGE-M3)
        # 5. Storage (Qdrant)
        # 6. Indexing (Postgres)
        # 7. RBAC tagging
        # 8. Knowledge graph extraction

        logger.debug(f"Processing document: {doc.uri}")
