from fastapi import APIRouter, Depends, HTTPException, status
from src.api.middleware.auth import get_current_tenant
from src.models.tenant import Tenant
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.post("/cancel")
async def cancel_subscription(
    tenant: Tenant = Depends(get_current_tenant),
):
    if not tenant.stripe_customer_id:
        logger.warning("tenant_has_no_stripe_customer tenant_id=%s", tenant.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer associated with this tenant"
        )

    logger.info("subscription_cancel_requested tenant_id=%s", tenant.id)

    return {
        "status": "pending",
        "message": "Please use the Stripe customer portal to cancel your subscription"
    }