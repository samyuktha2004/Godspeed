"""Polling adapters for logs, metrics, and error traces."""

import json
import hashlib
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from src.adapters.web_scraper import RawDocument
from src.config import settings

logger = logging.getLogger(__name__)


class LogAggregatorAdapter:
    """Adapter for aggregating and indexing server logs."""

    async def connect(self, credentials: dict) -> None:
        """Initialize log aggregator (no auth typically needed for local logs)."""
        pass

    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        Fetch ERROR/WARN logs since last sync.

        Args:
            space_id: Service name (e.g., "api-backend")
            last_sync_at: Only fetch logs after this timestamp

        Returns:
            List of RawDocuments representing log entries
        """
        docs = []

        # Get log file path for this service
        log_file = settings.integrations.log_file_paths.get(space_id)
        if not log_file:
            logger.warning(f"No log file configured for service: {space_id}")
            return []

        try:
            log_path = Path(log_file)
            if not log_path.exists():
                logger.warning(f"Log file not found: {log_file}")
                return []

            # Read log lines
            with open(log_path, "r") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Only index ERROR and WARN
                    if log_entry.get("level") not in ["ERROR", "WARN"]:
                        continue

                    # Check timestamp
                    entry_time = datetime.fromisoformat(log_entry.get("timestamp", ""))
                    if entry_time < last_sync_at:
                        continue

                    # Build content
                    content = f"""
Level: {log_entry.get('level')}
Service: {space_id}
Message: {log_entry.get('message')}

Trace ID: {log_entry.get('trace_id', 'N/A')}
Stack trace:
{log_entry.get('stacktrace', 'N/A')}

Context:
{json.dumps(log_entry.get('context', {}), indent=2)}
"""

                    # Create RawDocument
                    doc = RawDocument(
                        uri=f"logs://{space_id}/{log_entry.get('trace_id', log_entry.get('timestamp'))}",
                        source_type="log",
                        source_subtype="error_log",
                        title=f"[{log_entry.get('level')}] {space_id}: {log_entry.get('message', '')[:80]}",
                        content=content,
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        created_at=entry_time,
                        updated_at=datetime.utcnow(),
                        author_ids=["system"],
                        space_id=space_id,
                        tags=[log_entry.get("level", ""), space_id],
                        priority=5 if log_entry.get("level") == "ERROR" else 3,
                        ttl_seconds=86400 * 7,  # 1 week
                        raw_metadata=log_entry,
                    )
                    docs.append(doc)

        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")

        return docs


class MetricsAdapter:
    """Adapter for polling metrics and anomaly detection."""

    async def connect(self, credentials: dict) -> None:
        """Initialize metrics connection."""
        pass

    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        Fetch metrics with anomalies detected since last sync.

        Args:
            space_id: Metric source (e.g., "prometheus", "datadog")
            last_sync_at: Only fetch metrics with anomalies since this time

        Returns:
            List of RawDocuments representing metric anomalies
        """
        # Placeholder: would query Prometheus/Datadog APIs
        # For now, return empty list
        logger.info(f"Metrics polling for {space_id} - placeholder implementation")
        return []


class ErrorTraceAdapter:
    """Adapter for polling error traces from APM services."""

    async def connect(self, credentials: dict) -> None:
        """Initialize APM connection."""
        pass

    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        Fetch error groups with new occurrences since last sync.

        Args:
            space_id: APM source (e.g., "sentry", "datadog")
            last_sync_at: Only fetch errors after this time

        Returns:
            List of RawDocuments representing error traces
        """
        # Placeholder: would query Sentry/Datadog APIs
        # For now, return empty list
        logger.info(f"Error trace polling for {space_id} - placeholder implementation")
        return []


class BusinessDataAdapter:
    """Adapter for polling business data from ERP/CRM systems."""

    async def connect(self, credentials: dict) -> None:
        """Initialize business system connection."""
        pass

    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        Fetch updated business records since last sync.

        Args:
            space_id: Business domain (e.g., "sales", "inventory", "finance")
            last_sync_at: Only fetch records updated after this time

        Returns:
            List of RawDocuments representing business entities
        """
        # Placeholder: would query ERP/CRM APIs or databases
        # For now, return empty list
        logger.info(f"Business data polling for {space_id} - placeholder implementation")
        return []
