from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import defaultdict
import threading
from fastapi import Request

class InMemoryRateLimiter:
    """Simple in-memory rate limiter for development"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._locks = defaultdict(threading.Lock)
        self._requests = defaultdict(list)
    
    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed for given key.
        Returns (allowed: bool, retry_after_seconds: int)
        """
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


# Global limiter instance (replace with Redis in production)
rate_limiter = InMemoryRateLimiter(max_requests=100_000, window_seconds=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit by tenant + IP."""
    
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