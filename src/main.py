from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.api.middleware.rate_limit import RateLimitMiddleware, rate_limiter
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.middleware.request_id import RequestIDMiddleware
from src.api.middleware.error_handling import register_exception_handlers
from src.api.v1 import meter, usage, auth, checkout, billing, subscription, webhook
from src.api.health import router as health_router
from src.config.settings import get_settings
from src.config.logging import configure_logging
from src.config.cache import close_redis
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(log_level=settings.LOG_LEVEL)
    logger.info("app_startup version=0.1.0 env=%s", settings.ENVIRONMENT)
    yield
    await close_redis()
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIDMiddleware)
    
    register_exception_handlers(app)
    
    app.include_router(webhook.router, prefix=settings.API_V1_PREFIX)
    app.include_router(meter.router, prefix=settings.API_V1_PREFIX)
    app.include_router(usage.router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(billing.router, prefix=settings.API_V1_PREFIX)
    app.include_router(checkout.router, prefix=settings.API_V1_PREFIX)
    app.include_router(subscription.router, prefix=settings.API_V1_PREFIX)
    app.include_router(health_router)
    
    return app


app = create_app()
