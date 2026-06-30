"""Distributed locks to prevent concurrent syncing of same source."""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

import redis
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DistributedLock:
    """
    Redis-backed distributed lock for preventing concurrent operations on same resource.

    Prevents multiple Celery workers from syncing the same source simultaneously.
    """

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "locks"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.lock_id = str(uuid.uuid4())

    def _make_lock_key(self, resource: str) -> str:
        """Build lock key."""
        return f"{self.key_prefix}:{resource}"

    @staticmethod
    def _resource_ref(resource: str) -> str:
        return hashlib.sha256(resource.encode()).hexdigest()[:12]

    async def acquire(
        self,
        resource: str,
        timeout_seconds: int = 3600,
    ) -> bool:
        """
        Try to acquire a lock on a resource.

        Args:
            resource: Unique identifier (e.g., "notion:workspace-123")
            timeout_seconds: How long lock lasts before auto-releasing

        Returns:
            True if lock acquired, False if resource already locked
        """
        lock_key = self._make_lock_key(resource)

        # SET NX: only set if not exists
        # SET with EX: auto-expire after timeout
        result = self.redis.set(
            lock_key,
            self.lock_id,
            nx=True,
            ex=timeout_seconds,
        )
        acquired = result is not None
        logger.info(
            "distributed_lock_acquire",
            extra={"resource_ref": self._resource_ref(resource), "acquired": acquired, "timeout_seconds": timeout_seconds},
        )
        return acquired

    async def release(self, resource: str) -> bool:
        """
        Release a lock (only if we own it).

        Uses Lua script for atomic check-and-delete.
        """
        lock_key = self._make_lock_key(resource)

        # Lua script: delete only if value matches our lock_id (prevents freeing other locks)
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        script = self.redis.register_script(lua_script)
        result = script(keys=[lock_key], args=[self.lock_id])
        released = result > 0
        logger.info("distributed_lock_release", extra={"resource_ref": self._resource_ref(resource), "released": released})
        return released

    async def is_locked(self, resource: str) -> bool:
        """Check if resource is currently locked."""
        lock_key = self._make_lock_key(resource)
        locked = self.redis.exists(lock_key) > 0
        logger.info("distributed_lock_check", extra={"resource_ref": self._resource_ref(resource), "locked": locked})
        return locked

    async def wait_and_acquire(
        self,
        resource: str,
        timeout_seconds: int = 3600,
        max_wait_seconds: int = 300,
    ) -> bool:
        """
        Poll and wait until lock is available, then acquire it.

        Useful for ensuring sequential processing of the same resource.
        """
        wait_start = datetime.utcnow()
        wait_deadline = wait_start + timedelta(seconds=max_wait_seconds)

        while datetime.utcnow() < wait_deadline:
            if await self.acquire(resource, timeout_seconds):
                logger.info("distributed_lock_wait_acquired", extra={"resource_ref": self._resource_ref(resource)})
                return True

            # Back off: sleep 100ms before retrying
            await asyncio.sleep(0.1)

        logger.warning("distributed_lock_wait_timeout", extra={"resource_ref": self._resource_ref(resource), "max_wait_seconds": max_wait_seconds})
        return False


class LockPool:
    """Manage multiple locks efficiently."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.locks = {}  # resource -> DistributedLock instance

    def get_lock(self, resource: str) -> DistributedLock:
        """Get or create a lock for a resource."""
        if resource not in self.locks:
            self.locks[resource] = DistributedLock(self.redis)

        return self.locks[resource]

    async def acquire_many(
        self,
        resources: list[str],
        timeout_seconds: int = 3600,
    ) -> dict[str, bool]:
        """Try to acquire locks on multiple resources."""
        results = {}

        for resource in resources:
            lock = self.get_lock(resource)
            results[resource] = await lock.acquire(resource, timeout_seconds)

        return results

    async def release_all(self):
        """Release all locks held by this pool."""
        for resource, lock in self.locks.items():
            await lock.release(resource)

        logger.info("distributed_lock_pool_cleared", extra={"count": len(self.locks)})
        self.locks.clear()
