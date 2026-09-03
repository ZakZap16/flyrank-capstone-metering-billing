from src.repositories.usage_repo import UsageRepository
from src.repositories.subscription_repo import SubscriptionRepository
from src.repositories.plan_repo import PlanRepository
from src.models.usage_event import UsageType
from src.models.subscription import SubscriptionStatus
from src.schemas.meter import QuotaExceededError, PaymentRequiredError
from datetime import datetime, timezone
import uuid

class QuotaService:
    def __init__(self, session):
        self.usage_repo = UsageRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.plan_repo = PlanRepository(session)
    
    async def check_quota(
        self,
        tenant_id: uuid.UUID,
        usage_type: UsageType,
        requested_quantity: int,
    ) -> tuple[bool, dict]:
        """
        Check if the request is within quota
        Returns (allowed: bool, quota_info: dict)
        Raises QuotaExceededError or PaymentRequiredError
        """
        # Get active subscription
        subscription = await self.subscription_repo.get_active_by_tenant(tenant_id)
        if not subscription:
            raise PaymentRequiredError("No active subscription found")
        
        # Check subscription status
        if subscription.status != SubscriptionStatus.ACTIVE:
            if subscription.status == SubscriptionStatus.PAST_DUE:
                raise PaymentRequiredError("Subscription past due - payment required")
            elif subscription.status == SubscriptionStatus.CANCELED:
                raise PaymentRequiredError("Subscription canceled")
            else:
                raise PaymentRequiredError(f"Subscription status: {subscription.status.value}")
        
        # Get plan limits
        plan = await self.plan_repo.get_by_id(subscription.plan_id)
        if not plan:
            raise PaymentRequiredError("Plan not found")
        
        # Determine limit based on usage type
        if usage_type == UsageType.API_CALL:
            limit = plan.api_call_quota
        else:
            limit = plan.ai_token_quota
        
        # Get current month usage
        start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_used = await self.usage_repo.get_monthly_usage(tenant_id, usage_type, start_of_month)
        
        # Check quota
        will_exceed = current_used + requested_quantity > limit
        
        quota_info = {
            "usage_type": usage_type.value,
            "used": current_used,
            "limit": limit,
            "requested": requested_quantity,
            "remaining": max(0, limit - current_used),
            "will_exceed": will_exceed,
        }
        
        return (not will_exceed, quota_info)
    
    async def get_all_quotas(self, tenant_id: uuid.UUID) -> dict:
        """Get quota status for all usage types."""
        subscription = await self.subscription_repo.get_active_by_tenant(tenant_id)
        if not subscription:
            return {"error": "No active subscription"}
        
        plan = await self.plan_repo.get_by_id(subscription.plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_breakdown = await self.usage_repo.get_monthly_usage_breakdown(tenant_id, start_of_month)
        
        return {
            "plan": plan.name,
            "api_calls": {
                "used": usage_breakdown.get(UsageType.API_CALL, 0),
                "limit": plan.api_call_quota,
                "remaining": max(0, plan.api_call_quota - usage_breakdown.get(UsageType.API_CALL, 0)),
            },
            "ai_tokens": {
                "used": sum(value for key, value in usage_breakdown.items() if key != UsageType.API_CALL),
                "limit": plan.ai_token_quota,
                "remaining": max(0, plan.ai_token_quota - sum(
                    value for key, value in usage_breakdown.items() if key != UsageType.API_CALL
                )),
                "breakdown": {
                    key.value: value for key, value in usage_breakdown.items() if key != UsageType.API_CALL
                },
            },
        }