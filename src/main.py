from fastapi import FastAPI
from src.api.middleware.rate_limit import RateLimitMiddleware, rate_limiter
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.middleware.error_handling import register_exception_handlers
from src.api.v1 import meter, usage, auth, checkout, billing, subscription, webhook
from src.api.health import router as health_router
from src.config.settings import get_settings
from src.api.health import router as health_router
settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # Health status
    app.include_router(health_router)
    # Middleware order matters - outer to inner:
    app.add_middleware(RateLimitMiddleware)      # 1st: rate limiting
    app.add_middleware(IdempotencyMiddleware)    # 2nd: idempotency validation
    
    # Exception handlers
    register_exception_handlers(app)
    
    # Routers - webhook first (no auth), then auth-protected routes
    app.include_router(webhook.router, prefix=settings.API_V1_PREFIX)
    app.include_router(meter.router, prefix=settings.API_V1_PREFIX)
    app.include_router(usage.router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(billing.router, prefix=settings.API_V1_PREFIX)
    app.include_router(checkout.router, prefix=settings.API_V1_PREFIX)
    app.include_router(subscription.router, prefix=settings.API_V1_PREFIX)
    
    return app

app = create_app()