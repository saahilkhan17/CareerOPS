"""Async Redis client with a test seam. All users fail open (see cache.py)."""

from typing import Any

from redis import asyncio as aioredis

from app.core.config import get_settings

_override: Any | None = None


def set_redis_client(client: Any | None) -> None:
    """Override (tests: fakeredis) or clear the process-wide client."""
    global _override
    _override = client


_client: Any | None = None


def get_redis() -> Any:
    """Return the process-wide async Redis client (override wins in tests)."""
    global _client
    if _override is not None:
        return _override
    if _client is None:
        settings = get_settings()
        _client = aioredis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_timeout=2.0
        )
    return _client
