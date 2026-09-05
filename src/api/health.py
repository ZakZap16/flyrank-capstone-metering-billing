



import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.api.deps import get_db
from src.services.stripe_service import StripeService
from src.config.settings import get_settings, Settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def get_stripe_service() -> StripeService:
    return StripeService()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
    settings: Settings = Depends(get_settings),
):
    checks = {}
    
    # DB
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ready"
    except Exception:
        checks["database"] = "not_ready"
    
    # Stripe
    try:
        await stripe_service.get_customer("cus_test")  # lightweight call
        checks["stripe"] = "ready"
    except Exception:
        checks["stripe"] = "not_ready"
    
    # Redis (if rate limiter uses it)
    checks["rate_limiter"] = "ready"  # or check Redis
    
    all_ready = all(v == "ready" for v in checks.values())
    if not all_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)
    
    return {"status": "ready", "checks": checks}