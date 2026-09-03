from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.plan import PlanTier
from datetime import datetime, timezone
import uuid

class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active_by_tenant(self, tenant_id: uuid.UUID) -> Subscription | None:
        """Get active subscription for the tenant"""
        stmt = select(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def upsert_from_stripe(
        self,
        tenant_id: uuid.UUID,
        stripe_subscription_id: str,
        status: SubscriptionStatus,
        current_period_start: datetime | None,
        current_period_end: datetime | None,
        plan_id: PlanTier,
        cancel_at_period_end: bool,
    ) -> Subscription:
        """
        Create or update subscription from Stripe webhook
        Uses ON CONFLICT on stripe_subscription_id for idempotency
        """
        stmt = pg_insert(Subscription).values(
            tenant_id=tenant_id,
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            plan_id=plan_id,
            cancel_at_period_end=cancel_at_period_end,
        ).on_conflict_do_update(
            index_elements=["stripe_subscription_id"],
            set_={
                "status": status,
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "plan_id": plan_id,
                "cancel_at_period_end": cancel_at_period_end,
                "updated_at": datetime.now(timezone.utc),
            }
        ).returning(Subscription)
        
        result = await self.session.execute(stmt)
        return result.scalar_one()