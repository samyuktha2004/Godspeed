"""Redis caching layer for credentials, sync state, and frequently accessed data."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

import redis


class RedisCache:
    """Simple Redis cache with TTL support."""

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "cache"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    def _make_key(self, namespace: str, key: str) -> str:
        """Build cache key with namespace."""
        return f"{self.key_prefix}:{namespace}:{key}"

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Set cache value with optional TTL.

        Args:
            namespace: Logical grouping (e.g., "credentials", "sync_state")
            key: Cache key
            value: Value to cache (auto-serialized to JSON if not string)
            ttl_seconds: Time-to-live (None = no expiration)
        """
        cache_key = self._make_key(namespace, key)

        # Auto-serialize non-string values
        if isinstance(value, str):
            cache_value = value
        else:
            cache_value = json.dumps(value)

        if ttl_seconds:
            self.redis.setex(cache_key, ttl_seconds, cache_value)
        else:
            self.redis.set(cache_key, cache_value)

        return True

    async def get(
        self,
        namespace: str,
        key: str,
        deserialize: bool = True,
    ) -> Optional[Any]:
        """
        Get cache value.

        Args:
            namespace: Logical grouping
            key: Cache key
            deserialize: If True, attempt JSON deserialization
        """
        cache_key = self._make_key(namespace, key)
        value = self.redis.get(cache_key)

        if not value:
            return None

        value_str = value.decode('utf-8')

        if deserialize:
            try:
                return json.loads(value_str)
            except (json.JSONDecodeError, ValueError):
                return value_str

        return value_str

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete cache entry."""
        cache_key = self._make_key(namespace, key)
        self.redis.delete(cache_key)
        return True

    async def exists(self, namespace: str, key: str) -> bool:
        """Check if cache entry exists."""
        cache_key = self._make_key(namespace, key)
        return self.redis.exists(cache_key) > 0

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace."""
        pattern = self._make_key(namespace, "*")
        keys = self.redis.keys(pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0


class SyncStateCache(RedisCache):
    """Specialized cache for tracking last sync times per source."""

    def __init__(self, redis_client: redis.Redis):
        super().__init__(redis_client, key_prefix="sync_state")

    async def get_last_sync(self, source_type: str, space_id: str) -> Optional[datetime]:
        """Get last sync timestamp for a source/space."""
        key = f"{source_type}:{space_id}"
        timestamp_str = await self.get("last_sync", key, deserialize=False)

        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
        return None

    async def set_last_sync(self, source_type: str, space_id: str):
        """Update last sync timestamp to now."""
        key = f"{source_type}:{space_id}"
        await self.set("last_sync", key, datetime.utcnow().isoformat())

    async def get_last_full_sync(self, source_type: str, space_id: str) -> Optional[datetime]:
        """Get last full (non-incremental) sync timestamp."""
        key = f"{source_type}:{space_id}"
        timestamp_str = await self.get("full_sync", key, deserialize=False)

        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
        return None

    async def set_last_full_sync(self, source_type: str, space_id: str):
        """Update last full sync timestamp to now."""
        key = f"{source_type}:{space_id}"
        await self.set("full_sync", key, datetime.utcnow().isoformat())


class CredentialCache(RedisCache):
    """Specialized cache for storing integration credentials (encrypted in production)."""

    def __init__(self, redis_client: redis.Redis):
        super().__init__(redis_client, key_prefix="credentials")
        # In production, use redis-py with encryption or a separate vault service
        # For now, TTL prevents long-term exposure

    async def get_credentials(self, integration_type: str, org_id: str) -> Optional[dict]:
        """Get cached credentials for an integration."""
        key = f"{integration_type}:{org_id}"
        return await self.get("creds", key, deserialize=True)

    async def set_credentials(
        self,
        integration_type: str,
        org_id: str,
        credentials: dict,
        ttl_seconds: int = 3600,  # 1 hour default
    ):
        """Cache credentials with short TTL (should fetch fresh when possible)."""
        key = f"{integration_type}:{org_id}"
        await self.set("creds", key, credentials, ttl_seconds=ttl_seconds)

    async def clear_credentials(self, integration_type: str, org_id: str):
        """Revoke cached credentials immediately."""
        key = f"{integration_type}:{org_id}"
        await self.delete("creds", key)
