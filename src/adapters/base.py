"""Base adapter interface and adapter registry."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, list

from src.adapters.web_scraper import RawDocument


class BaseSourceAdapter(ABC):
    """Base class for all source adapters."""

    @abstractmethod
    async def connect(self, credentials: dict) -> None:
        """Authenticate and validate connection."""
        pass

    @abstractmethod
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """Full crawl for initial indexing."""
        pass

    @abstractmethod
    async def fetch_incremental(
        self, space_id: str, last_sync_at: datetime
    ) -> list[RawDocument]:
        """Fetch only changed/new items since last sync."""
        pass

    @abstractmethod
    async def fetch_by_query(self, query: str) -> list[RawDocument]:
        """Search capability (if source supports it)."""
        pass


class AdapterRegistry:
    """Registry for all source adapters."""

    def __init__(self):
        self.adapters = {}

    def register(self, source_type: str, adapter_class):
        """Register an adapter for a source type."""
        self.adapters[source_type] = adapter_class

    def get(self, source_type: str) -> Optional[BaseSourceAdapter]:
        """Get an adapter by source type."""
        adapter_class = self.adapters.get(source_type)
        if not adapter_class:
            return None
        return adapter_class()

    def list_adapters(self) -> list[str]:
        """List all registered adapters."""
        return list(self.adapters.keys())


# Global registry
_adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry."""
    return _adapter_registry


def register_adapter(source_type: str, adapter_class):
    """Register an adapter globally."""
    _adapter_registry.register(source_type, adapter_class)
