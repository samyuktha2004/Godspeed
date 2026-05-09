import time
from typing import Optional

class Cache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry and (time.monotonic() - entry[1]) < self._ttl:
            return entry[0]
        if entry:
            del self._store[key]
        return None

    def set(self, key: str, value: str) -> None:
        self._store[key] = (value, time.monotonic())

    def clear(self) -> None:
        self._store.clear()