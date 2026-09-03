from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status
import uuid

class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Validate Idempotency-Key header on mutating endpoints."""
    
    IDEMPOTENCY_PATHS = ["/api/v1/meter"]
    IDEMPOTENCY_METHODS = ["POST", "PUT", "PATCH"]
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.IDEMPOTENCY_PATHS and request.method in self.IDEMPOTENCY_METHODS:
            idempotency_key = request.headers.get("Idempotency-Key")
            if not idempotency_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Idempotency-Key header is required"
                )
            try:
                uuid.UUID(idempotency_key, version=4)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Idempotency-Key must be a valid UUID v4"
                )
        response = await call_next(request)
        return response