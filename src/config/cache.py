import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None
_last_connection_attempt: float = 0
_connection_cooldown: float = 5.0


async def get_redis() -> aioredis.Redis | None:
    global _pool, _last_connection_attempt
    
    if _pool is not None:
        return _pool
    
    now = time.monotonic()
    if now - _last_connection_attempt < _connection_cooldown:
        return None
    
    _last_connection_attempt = now
    
    try:
        settings = get_settings()
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await _pool.ping()
        return _pool
    except Exception as e:
        logger.warning("redis_unavailable error=%s", str(e)[:100])
        _pool = None
        return None


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def cache_get(key: str) -> dict | None:
    try:
        r = await get_redis()
        if r is None:
            return None
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception:
        logger.debug("cache_get_miss key=%s", key)
    return None


async def cache_set(key: str, value: dict, ttl_seconds: int = 60) -> None:
    try:
        r = await get_redis()
        if r is None:
            return
        await r.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception:
        logger.debug("cache_set_failed key=%s", key)


async def cache_delete(key: str) -> None:
    try:
        r = await get_redis()
        if r is None:
            return
        await r.delete(key)
    except Exception:
        logger.debug("cache_delete_failed key=%s", key)


async def cache_delete_pattern(pattern: str) -> None:
    try:
        r = await get_redis()
        if r is None:
            return
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.debug("cache_delete_pattern_failed pattern=%s", pattern)


IDEMPOTENCY_TTL_SECONDS = 86400


async def check_idempotency_key(tenant_id: str, key: str, usage_type: str) -> dict | None:
    cache_key = f"idem:{tenant_id}:{key}:{usage_type}"
    return await cache_get(cache_key)


async def store_idempotency_response(tenant_id: str, key: str, usage_type: str, response: dict) -> None:
    cache_key = f"idem:{tenant_id}:{key}:{usage_type}"
    await cache_set(cache_key, response, ttl_seconds=IDEMPOTENCY_TTL_SECONDS)
