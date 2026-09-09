from fastapi import APIRouter, Depends, HTTPException, status
from src.api.middleware.auth import get_current_tenant
from src.api.deps import get_db
from src.models.tenant import Tenant
from src.services.stripe_service import StripeService
from src.config.settings import get_settings, Settings
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


def get_stripe_service() -> StripeService:
    return StripeService()

@router.post("/portal")
async def create_portal_session(
    tenant: Tenant = Depends(get_current_tenant),
    stripe_service: StripeService = Depends(get_stripe_service),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db)
):
    if not tenant.stripe_customer_id:
        logger.warning("tenant_has_no_stripe_customer tenant_id=%s", tenant.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer associated with this tenant"
        )
    
    try:
        portal_session = await stripe_service.create_portal_session(
            customer_id=tenant.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/billing"
        )
        
        logger.info("billing_portal_session_created tenant_id=%s stripe_customer_id=%s", 
                   tenant.id, tenant.stripe_customer_id)
        
        return {"url": portal_session.url}
    except Exception as e:
        logger.exception("billing_portal_creation_failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )
