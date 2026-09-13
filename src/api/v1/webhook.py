from fastapi import APIRouter, Request, HTTPException, Depends, status
from src.services.quota_service import QuotaService
from src.services.auth_service import AuthService
from src.services.stripe_service import StripeService
from src.repositories.stripe_event_repo import StripeEventRepository
from src.repositories.tenant_repo import TenantRepository
from src.repositories.subscription_repo import SubscriptionRepository
from src.repositories.plan_repo import PlanRepository
from src.models.tenant import Tenant
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.plan import PlanTier
from src.config.settings import get_settings, Settings
from src.api.deps import get_db, get_stripe_service
from src.config.cache import cache_delete, cache_delete_pattern
from sqlalchemy.ext.asyncio import AsyncSession
import inspect
import logging
import stripe
from uuid import UUID
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_SUBSCRIPTION_CACHE_PREFIX = "sub:"


async def _invalidate_subscription_cache(tenant_id: UUID) -> None:
    await cache_delete(f"{_SUBSCRIPTION_CACHE_PREFIX}{tenant_id}")



def get_stripe_event_repo(db: AsyncSession = Depends(get_db)) -> StripeEventRepository:
    return StripeEventRepository(db)


def get_quota_service(db: AsyncSession = Depends(get_db)) -> QuotaService:
    return QuotaService(db)


def get_tenant_repo(db: AsyncSession = Depends(get_db)) -> TenantRepository:
    return TenantRepository(db)


def get_subscription_repo(db: AsyncSession = Depends(get_db)) -> SubscriptionRepository:
    return SubscriptionRepository(db)


def get_plan_repo(db: AsyncSession = Depends(get_db)) -> PlanRepository:
    return PlanRepository(db)


def get_auth_service() -> AuthService:
    return AuthService()


def _extract_event_payload(event_obj) -> dict:
    if isinstance(event_obj, dict):
        return event_obj
    if hasattr(event_obj, "to_dict"):
        return event_obj.to_dict()
    if hasattr(event_obj, "__dict__"):
        return {k: v for k, v in event_obj.__dict__.items() if not k.startswith("_")}
    return {"raw": str(event_obj)}


def _verify_signature_or_raise(
    stripe_service: StripeService,
    payload: bytes,
    sig_header: str,
    secret: str,
):
    try:
        return stripe_service.verify_webhook_signature(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError as e:
        logger.error("webhook_signature_verification_failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_service: StripeService = Depends(get_stripe_service),
    stripe_repo: StripeEventRepository = Depends(get_stripe_event_repo),
    quota_service: QuotaService = Depends(get_quota_service),
    tenant_repo: TenantRepository = Depends(get_tenant_repo),
    subscription_repo: SubscriptionRepository = Depends(get_subscription_repo),
    plan_repo: PlanRepository = Depends(get_plan_repo),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        logger.warning("missing_stripe_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    event = _verify_signature_or_raise(
        stripe_service, payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    if await stripe_repo.is_processed(event.id):
        logger.info("webhook_event_already_processed event_id=%s", event.id)
        return {"status": "already_processed"}

    try:
        await _process_stripe_event(
            event,
            stripe_service,
            quota_service,
            tenant_repo,
            subscription_repo,
            plan_repo,
            auth_service,
            settings,
        )

        await stripe_repo.mark_processed(
            event.id,
            event.type,
            _extract_event_payload(event.data.object),
        )

        logger.info(
            "webhook_event_processed event_id=%s event_type=%s",
            event.id,
            event.type,
        )
        return {"status": "success"}
    except Exception as e:
        logger.exception("webhook_processing_failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from e


async def _process_stripe_event(
    event: stripe.Event,
    stripe_service: StripeService,
    quota_service: QuotaService,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    plan_repo: PlanRepository,
    auth_service: AuthService,
    settings: Settings
):
    event_handlers = {
        "checkout.session.completed": _handle_checkout_completed,
        "invoice.payment_succeeded": _handle_payment_succeeded,
        "invoice.payment_failed": _handle_payment_failed,
        "customer.subscription.created": _handle_subscription_created,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "customer.subscription.trial_will_end": _handle_subscription_trial_will_end,
        "invoice.upcoming": _handle_invoice_upcoming,
    }
    
    handler = event_handlers.get(event.type)
    if handler:
        sig = inspect.signature(handler)
        available_args = {
            "stripe_service": stripe_service,
            "quota_service": quota_service,
            "tenant_repo": tenant_repo,
            "subscription_repo": subscription_repo,
            "plan_repo": plan_repo,
            "auth_service": auth_service,
            "settings": settings,
        }
        first_param = list(sig.parameters.values())[0]
        positional_args = [event.data.object]
        for param_name in list(sig.parameters.keys())[1:]:
            if param_name in available_args:
                positional_args.append(available_args[param_name])
        await handler(*positional_args)
    else:
        logger.info("unhandled_stripe_event_type event_type=%s", event.type)


async def _handle_checkout_completed(
    session: stripe.checkout.Session,
    stripe_service: StripeService,
    quota_service: QuotaService,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    plan_repo: PlanRepository,
    auth_service: AuthService,
    settings: Settings
):
    metadata = session.metadata or {}
    tenant_id_str = metadata.get("tenant_id")
    customer_id = session.customer
    subscription_id = session.subscription
    
    if tenant_id_str:
        try:
            tenant_id = UUID(tenant_id_str)
            tenant = await tenant_repo.get(tenant_id)
            if not tenant:
                logger.error("tenant_not_found_in_metadata tenant_id=%s", tenant_id_str)
                return
        except ValueError:
            logger.error("invalid_tenant_id_in_metadata tenant_id=%s", tenant_id_str)
            return
    else:
        tenant = await _create_new_tenant_from_checkout(
            session, stripe_service, tenant_repo, quota_service, auth_service, settings
        )
        tenant_id = tenant.id
    
    await _create_or_update_subscription(
        tenant_id, subscription_id, customer_id, session, subscription_repo, settings
    )
    
    await _invalidate_subscription_cache(tenant_id)


async def _create_new_tenant_from_checkout(
    session: stripe.checkout.Session,
    stripe_service: StripeService,
    tenant_repo: TenantRepository,
    quota_service: QuotaService,
    auth_service: AuthService,
    settings: Settings
) -> Tenant:
    customer = await stripe_service.get_customer(session.customer)
    
    plain_key, hashed_key = auth_service.generate_api_key()
    
    created_tenant = await tenant_repo.create(
        name=customer.email.split("@")[0] if customer.email else "New Tenant",
        email=customer.email,
        api_key_hash=hashed_key,
        stripe_customer_id=customer.id,
    )
    
    logger.info("new_tenant_created_via_checkout tenant_id=%s email=%s", 
                created_tenant.id, customer.email)
    
    return created_tenant


async def _create_or_update_subscription(
    tenant_id: UUID,
    subscription_id: str,
    customer_id: str,
    session: stripe.checkout.Session,
    subscription_repo: SubscriptionRepository,
    settings: Settings
):
    existing_sub = await subscription_repo.get_by_stripe_id(subscription_id)
    
    plan_tier = PlanTier.FREE
    if session and hasattr(session, 'display_items') and session.display_items:
        if len(session.display_items) > 0:
            try:
                price_id = session.display_items[0].plan.price.id
                plan_tier = PlanTier.PRO if price_id == settings.STRIPE_PRICE_ID_PRO else PlanTier.FREE
            except (AttributeError, IndexError):
                plan_tier = PlanTier.FREE
    
    await subscription_repo.upsert_from_stripe(
        tenant_id=tenant_id,
        stripe_subscription_id=subscription_id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        plan_id=plan_tier,
        cancel_at_period_end=False,
    )


async def _handle_payment_succeeded(
    invoice: stripe.Invoice,
    quota_service: QuotaService,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    settings: Settings
):
    if invoice.subscription:
        subscription = await subscription_repo.get_by_stripe_id(invoice.subscription)
        if subscription:
            subscription.status = SubscriptionStatus.ACTIVE
            await subscription_repo.update(subscription)
            
            await _invalidate_subscription_cache(subscription.tenant_id)
            
            tenant = await tenant_repo.get(subscription.tenant_id)
            if tenant:
                logger.info("payment_succeeded_restoring_quota tenant_id=%s", tenant.id)


async def _handle_payment_failed(
    invoice: stripe.Invoice,
    quota_service: QuotaService,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    settings: Settings
):
    if invoice.subscription:
        subscription = await subscription_repo.get_by_stripe_id(invoice.subscription)
        if subscription:
            subscription.status = SubscriptionStatus.PAST_DUE
            await subscription_repo.update(subscription)
            
            await _invalidate_subscription_cache(subscription.tenant_id)
            
            logger.info("payment_failed_setting_past_due tenant_id=%s subscription_id=%s", 
                       subscription.tenant_id, subscription.id)


async def _handle_subscription_created(
    subscription: stripe.Subscription,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    plan_repo: PlanRepository,
    quota_service: QuotaService,
    settings: Settings
):
    db_sub = await subscription_repo.get_by_stripe_id(subscription.id)
    if db_sub:
        db_sub.status = SubscriptionStatus(subscription.status)
        await subscription_repo.update(db_sub)
        await _invalidate_subscription_cache(db_sub.tenant_id)
        logger.info("subscription_created subscription_id=%s", subscription.id)
    else:
        price_id = None
        if subscription.items.data:
            price_id = subscription.items.data[0].price.id
        plan_tier = PlanTier.PRO if price_id == settings.STRIPE_PRICE_ID_PRO else PlanTier.FREE
        
        new_sub = Subscription(
            tenant_id=UUID(subscription.metadata.get("tenant_id")) if subscription.metadata.get("tenant_id") else None,
            stripe_subscription_id=subscription.id,
            plan_id=plan_tier,
            status=SubscriptionStatus(subscription.status),
            current_period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            cancel_at_period_end=subscription.cancel_at_period_end,
            canceled_at=datetime.fromtimestamp(subscription.canceled_at, tz=timezone.utc) if subscription.canceled_at else None,
        )
        await subscription_repo.create(new_sub)
        if new_sub.tenant_id:
            await _invalidate_subscription_cache(new_sub.tenant_id)
        logger.info("subscription_created_new_record subscription_id=%s", subscription.id)


async def _handle_subscription_updated(
    subscription: stripe.Subscription,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    plan_repo: PlanRepository,
    quota_service: QuotaService,
    settings: Settings
):
    db_sub = await subscription_repo.get_by_stripe_id(subscription.id)
    if db_sub:
        db_sub.status = SubscriptionStatus(subscription.status)
        db_sub.current_period_start = datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc)
        db_sub.current_period_end = datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc)
        db_sub.cancel_at_period_end = subscription.cancel_at_period_end
        
        if subscription.items.data:
            new_price_id = subscription.items.data[0].price.id
            if new_price_id != db_sub.plan_id.value:
                new_plan_tier = PlanTier.PRO if new_price_id == settings.STRIPE_PRICE_ID_PRO else PlanTier.FREE
                db_sub.plan_id = new_plan_tier
        
        await subscription_repo.update(db_sub)
        await _invalidate_subscription_cache(db_sub.tenant_id)
        logger.info("subscription_updated subscription_id=%s new_status=%s", 
                   subscription.id, subscription.status)


async def _handle_subscription_deleted(
    subscription: stripe.Subscription,
    subscription_repo: SubscriptionRepository,
    tenant_repo: TenantRepository
):
    db_sub = await subscription_repo.get_by_stripe_id(subscription.id)
    if db_sub:
        db_sub.status = SubscriptionStatus.CANCELED
        db_sub.canceled_at = datetime.fromtimestamp(subscription.canceled_at, tz=timezone.utc) if subscription.canceled_at else datetime.now(timezone.utc)
        await subscription_repo.update(db_sub)
        await _invalidate_subscription_cache(db_sub.tenant_id)
        
        logger.info("subscription_canceled subscription_id=%s tenant_id=%s", 
                   subscription.id, db_sub.tenant_id)


async def _handle_subscription_trial_will_end(
    subscription: stripe.Subscription,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    settings: Settings
):
    logger.info("subscription_trial_will_end subscription_id=%s tenant_id=%s", 
               subscription.id, subscription.metadata.get("tenant_id"))


async def _handle_invoice_upcoming(
    invoice: stripe.Invoice,
    quota_service: QuotaService,
    tenant_repo: TenantRepository,
    subscription_repo: SubscriptionRepository,
    settings: Settings
):
    logger.info("invoice_upcoming invoice_id=%s amount_due=%s", 
               invoice.id, invoice.amount_due)
