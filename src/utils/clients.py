"""Process-wide singleton clients for Redis and Qdrant.

Replaces the pattern of creating a fresh client per request — which adds
50–200 ms of TCP/TLS setup per call and churns sockets into TIME_WAIT under
load. Both clients are cheap to construct (no IO at __init__ time), so they
can be initialised eagerly in the FastAPI lifespan or lazily on first use.

Lifecycle
---------
- `init_clients()`  — called from `main.py`'s lifespan on app startup.
- `close_clients()` — called from the same lifespan on shutdown.
- `get_redis()` / `get_qdrant()` — call from any request path. Lazily
  initialises the singleton if the lifespan hook hasn't run yet (e.g. when
  running tests that bypass lifespan).

Important
---------
- DO NOT call `aclose()` / `close()` on the returned clients. The lifespan
  shutdown hook owns their lifetime.
- Pool sizing: `max_connections=20` per uvicorn worker is generous for our
  workloads. If you run N workers, total Redis connections = N × 20.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_redis: Optional[aioredis.Redis] = None
_qdrant: Optional[AsyncQdrantClient] = None

_redis_lock = asyncio.Lock()
_qdrant_lock = asyncio.Lock()


def _build_redis() -> aioredis.Redis:
    logger.info("redis_client_build")
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        max_connections=20,
    )


def _build_qdrant() -> AsyncQdrantClient:
    if settings.qdrant_url:
        logger.info("qdrant_client_build", extra={"mode": "url"})
        return AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    logger.info("qdrant_client_build", extra={"mode": "host_port"})
    return AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )


async def init_clients() -> None:
    """Eagerly construct the singletons. Idempotent."""
    global _redis, _qdrant
    if _redis is None:
        _redis = _build_redis()
    if _qdrant is None:
        _qdrant = _build_qdrant()
    logger.info("shared_clients_initialized")


async def close_clients() -> None:
    """Close the singletons. Called from app shutdown."""
    global _redis, _qdrant
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            logger.exception("redis_client_close_failed")
        _redis = None
    if _qdrant is not None:
        try:
            await _qdrant.close()
        except Exception:
            logger.exception("qdrant_client_close_failed")
        _qdrant = None
    logger.info("shared_clients_closed")


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client. Lazily initialised."""
    global _redis
    if _redis is None:
        async with _redis_lock:
            if _redis is None:
                logger.info("redis_client_lazy_init")
                _redis = _build_redis()
    return _redis


def get_qdrant() -> AsyncQdrantClient:
    """Return the shared async Qdrant client. Lazily initialised."""
    global _qdrant
    if _qdrant is None:
        # No asyncio.Lock needed: AsyncQdrantClient construction is sync and
        # cheap. Worst case two callers race and one wins — the loser's
        # client is discarded with no IO performed.
        logger.info("qdrant_client_lazy_init")
        _qdrant = _build_qdrant()
    return _qdrant
