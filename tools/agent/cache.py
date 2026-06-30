import time
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Cache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry and (time.monotonic() - entry[1]) < self._ttl:
            logger.info("tools_cache_hit")
            return entry[0]
        if entry:
            del self._store[key]
            logger.info("tools_cache_expired")
        else:
            logger.info("tools_cache_miss")
        return None

    def set(self, key: str, value: str) -> None:
        self._store[key] = (value, time.monotonic())
        logger.info("tools_cache_set", extra={"size": len(self._store)})

    def clear(self) -> None:
        logger.info("tools_cache_cleared", extra={"size_before": len(self._store)})
        self._store.clear()