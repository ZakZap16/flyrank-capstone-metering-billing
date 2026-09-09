from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status
import uuid


class IdempotencyMiddleware(BaseHTTPMiddleware):

    IDEMPOTENCY_PATHS = ["/api/v1/meter"]
    IDEMPOTENCY_METHODS = ["POST", "PUT", "PATCH"]

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.IDEMPOTENCY_PATHS and request.method in self.IDEMPOTENCY_METHODS:
            idempotency_key = request.headers.get("Idempotency-Key")
            if not idempotency_key:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Idempotency-Key header is required"},
                )
            try:
                uuid.UUID(idempotency_key, version=4)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Idempotency-Key must be a valid UUID v4"},
                )
        response = await call_next(request)
        return response
