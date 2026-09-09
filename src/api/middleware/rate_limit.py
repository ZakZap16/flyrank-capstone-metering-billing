import time
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.cache import get_redis

logger = logging.getLogger(__name__)


class RedisRateLimiter:

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        try:
            r = await get_redis()
            if r is None:
                return True, 0
            
            now = time.time()
            window_start = now - self.window_seconds

            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {f"{now}": now})
            pipe.expire(key, self.window_seconds + 1)
            results = await pipe.execute()

            current_count = results[1]

            if current_count >= self.max_requests:
                oldest = await r.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + self.window_seconds - now) + 1
                    return False, max(retry_after, 1)
                return False, self.window_seconds

            return True, 0
        except Exception:
            logger.warning("rate_limiter_redis_unavailable key=%s", key)
            return True, 0


_rate_limiter = None


def _init_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        from src.config.settings import get_settings
        settings = get_settings()
        _rate_limiter = RedisRateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
    return _rate_limiter


rate_limiter = _init_rate_limiter()


class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"rate:{tenant_id}:{client_ip}"

        allowed, retry_after = await rate_limiter.is_allowed(rate_key)
        if not allowed:
            return Response(
                content='{"error": "rate_limited", "detail": "Too many requests"}',
                status_code=429,
                headers={"Retry-After": str(retry_after), "Content-Type": "application/json"},
            )

        response = await call_next(request)
        return response
