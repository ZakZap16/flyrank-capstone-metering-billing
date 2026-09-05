from fastapi import APIRouter, Depends, HTTPException, status
from src.api.middleware.auth import get_current_tenant
from src.api.deps import get_db
from src.models.tenant import Tenant
from src.services.stripe_service import StripeService
from src.config.settings import get_settings, Settings
from src.schemas.checkout import CheckoutRequest
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/checkout", tags=["checkout"])


def get_stripe_service() -> StripeService:
    return StripeService()

@router.post("/session")
async def create_checkout_session(
    request: CheckoutRequest,
    tenant: Tenant = Depends(get_current_tenant),
    stripe_service: StripeService = Depends(get_stripe_service),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Stripe checkout session for plan subscription.
    Requires authentication (X-Tenant-ID header).
    """
    # Validate plan_tier
    if request.plan_tier not in ["free", "pro"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan_tier. Must be 'free' or 'pro'"
        )
    
    # Get or create Stripe customer
    if not tenant.stripe_customer_id:
        # Create new Stripe customer for this tenant
        customer = await stripe_service.create_customer(
            email=tenant.email,
            metadata={"tenant_id": str(tenant.id)}
        )
        # Update tenant with Stripe customer ID
        tenant.stripe_customer_id = customer.id
        await db.commit()
        await db.refresh(tenant)
        logger.info("stripe_customer_created_for_tenant tenant_id=%s stripe_customer_id=%s", 
                   tenant.id, customer.id)
    
    # Determine price ID based on requested plan
    price_id = (
        settings.STRIPE_PRICE_ID_PRO 
        if request.plan_tier == "pro" 
        else settings.STRIPE_PRICE_ID_FREE
    )
    
    # Build URLs - in production, these would come from settings
    success_url = f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.FRONTEND_URL}/billing/cancel"
    
    # Create checkout session
    try:
        session = await stripe_service.create_checkout_session(
            customer_id=tenant.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(tenant.id),
                "requested_plan_tier": request.plan_tier
            }
        )
        
        logger.info("checkout_session_created tenant_id=%s session_id=%s plan_tier=%s", 
                   tenant.id, session.id, request.plan_tier)
        
        return {
            "checkout_session_id": session.id,
            "url": session.url
        }
    except Exception as e:
        logger.exception("checkout_session_creation_failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )