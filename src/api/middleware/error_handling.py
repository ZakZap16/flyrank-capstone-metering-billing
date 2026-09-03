from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from src.schemas.meter import QuotaExceededError, PaymentRequiredError
from pydantic import ValidationError

def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers for the FastAPI app."""
    
    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "quota_exceeded",
                "detail": {
                    "usage_type": exc.usage_type.value,
                    "used": exc.used,
                    "limit": exc.limit,
                    "requested": exc.requested,
                },
                "retry_after_seconds": 86400,
            },
            headers={"Retry-After": "86400"},
        )
    
    @app.exception_handler(PaymentRequiredError)
    async def payment_required_handler(request: Request, exc: PaymentRequiredError):
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={
                "error": "payment_required",
                "detail": str(exc),
            },
        )
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "detail": exc.errors(),
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred",
            },
        )