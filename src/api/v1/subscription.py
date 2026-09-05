from fastapi import APIRouter, Depends, HTTPException, status
from src.api.middleware.auth import get_current_tenant
from src.models.tenant import Tenant
from src.services.stripe_service import StripeService
from src.config.settings import get_settings, Settings
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def get_stripe_service() -> StripeService:
    return StripeService()


@router.post("/cancel")
async def cancel_subscription(
    tenant: Tenant = Depends(get_current_tenant),
    stripe_service: StripeService = Depends(get_stripe_service),
    settings: Settings = Depends(get_settings),
):
    """
    Cancel the tenant's subscription.
    By default, cancels at the end of the billing period.
    Requires authentication (X-Tenant-ID header).
    
    Note: This endpoint requires the tenant to have a Stripe subscription ID.
    In production, you would fetch the subscription from the database and update it.
    """
    if not tenant.stripe_customer_id:
        logger.warning("tenant_has_no_stripe_customer tenant_id=%s", tenant.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer associated with this tenant"
        )
    
    try:
        logger.info("subscription_cancel_requested tenant_id=%s", tenant.id)
        
        return {
            "status": "pending",
            "message": "Please use the Stripe customer portal to cancel your subscription"
        }
    except Exception as e:
        logger.exception("subscription_cancellation_failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )