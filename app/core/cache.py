"""Small JSON cache over Redis. Every operation fails open (miss/skip)."""

import json
import logging
from typing import Any

from app.core import redis_client

logger = logging.getLogger("careerops.cache")

ANALYTICS_PREFIX = "analytics:"


def cache_key(*parts: str) -> str:
    """Build a namespaced cache key from parts."""
    safe = [p.replace(" ", "_") for p in parts]
    return ANALYTICS_PREFIX + ":".join(safe)


async def cache_get(key: str) -> Any | None:
    """Return the parsed JSON value, or None on miss/error."""
    try:
        raw = await redis_client.get_redis().get(key)
    except Exception as exc:
        logger.warning("cache get failed (%s): %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Store a JSON-serializable value. Failures are logged and ignored."""
    try:
        await redis_client.get_redis().set(key, json.dumps(value), ex=ttl)
    except Exception as exc:
        logger.warning("cache set failed (%s): %s", key, exc)


async def invalidate_analytics() -> None:
    """Drop all analytics cache entries (post-ingest/import). Fail-open."""
    try:
        client = redis_client.get_redis()
        keys = [k async for k in client.scan_iter(f"{ANALYTICS_PREFIX}*")]
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        logger.warning("cache invalidate failed: %s", exc)


async def invalidate_user_gap(user_id: str) -> None:
    """Drop one user's cached gap (profile edits). Fail-open."""
    try:
        client = redis_client.get_redis()
        keys = [k async for k in client.scan_iter(f"{ANALYTICS_PREFIX}gap:{user_id}*")]
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        logger.warning("gap invalidate failed: %s", exc)
