from fastapi import FastAPI
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.middleware.error_handling import register_exception_handlers
from src.api.v1 import meter, usage, auth
from src.config.settings import get_settings

settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Middleware order matters - outer to inner:
    app.add_middleware(RateLimitMiddleware)      # 1st: rate limiting
    app.add_middleware(IdempotencyMiddleware)    # 2nd: idempotency validation
    
    # Exception handlers
    register_exception_handlers(app)
    
    # Routers
    app.include_router(meter.router, prefix=settings.API_V1_PREFIX)
    app.include_router(usage.router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    return app

app = create_app()