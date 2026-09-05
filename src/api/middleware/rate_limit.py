"""Rate limiting middleware using in-memory storage with optional Redis backend."""
from collections import defaultdict
import threading
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class InMemoryRateLimiter:
    """Simple in-memory rate limiter for development."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._locks = defaultdict(threading.Lock)
        self._requests = defaultdict(list)
    
    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed for given key. Returns (allowed, retry_after_seconds)."""
        current_time = time.time()
        with self._locks[key]:
            # Clean old requests outside the window
            self._requests[key] = [
                timestamp for timestamp in self._requests[key] 
                if timestamp > current_time - self.window_seconds
            ]
            
            if len(self._requests[key]) >= self.max_requests:
                oldest_timestamp = self._requests[key][0]
                retry_after = int(oldest_timestamp + self.window_seconds - current_time) + 1
                return False, retry_after
            
            self._requests[key].append(current_time)
            return True, 0


# Global rate limiter instance - configured from settings
_settings = None

def _get_settings():
    global _settings
    if _settings is None:
        from src.config.settings import get_settings
        _settings = get_settings()
    return _settings

_rate_limiter = None

def _init_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        settings = _get_settings()
        _rate_limiter = InMemoryRateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
        )
    return _rate_limiter

rate_limiter = _init_rate_limiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit by tenant + IP using in-memory storage.
    
    Note: For production with multi-instance support, consider replacing this
    with Redis-backed rate limiting via slowapi or a dedicated service.
    """
    
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"{tenant_id}:{client_ip}"
        
        allowed, retry_after = rate_limiter.is_allowed(rate_key)
        if not allowed:
            return Response(
                content='{"error": "rate_limited", "detail": "Too many requests"}',
                status_code=429,
                headers={"Retry-After": str(retry_after), "Content-Type": "application/json"},
            )
        
        response = await call_next(request)
        return response