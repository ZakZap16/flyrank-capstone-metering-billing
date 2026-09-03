from src.repositories.usage_repo import UsageRepository
from src.services.quota_service import QuotaService
from src.services.cost_service import CostService
from src.models.usage_event import UsageType, UsageEvent
from src.schemas.meter import QuotaExceededError, PaymentRequiredError
from datetime import datetime, timezone

import uuid

class MeterService:
    """Core metering service - orchestrates quota check, cost calc, and recording."""
    
    def __init__(self, session):
        self.usage_repo = UsageRepository(session)
        self.quota_service = QuotaService(session)
        self.cost_service = CostService()
    
    async def record(
        self,
        tenant_id: uuid.UUID,
        usage_type: UsageType,
        qty: int,
        idempotency_key: str,
        req_ip: str | None = None,
        user_agent: str | None = None,
    ) -> UsageEvent:
        """
        Record a usage event with full quota enforcement and idempotency.
        
        Raises:
            QuotaExceededError: If request would exceed quota (429)
            PaymentRequiredError: If subscription not active (402)
        """
        # Check quota FIRST (before any DB write)
        allowed, quota_info = await self.quota_service.check_quota(
            tenant_id, usage_type, qty
        )
        if not allowed:
            raise QuotaExceededError(
                usage_type=usage_type,
                used=quota_info["used"],
                limit=quota_info["limit"],
                requested=qty,
            )
        
        # Calculate cost
        cost_microunits = self.cost_service.calculate(usage_type, qty)
        
        # Record usage (using atomic)
        event = await self.usage_repo.record_usage(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            usage_type=usage_type,
            quantity=qty,
            cost_microunits=cost_microunits,
            request_ip=req_ip,
            user_agent=user_agent,
        )
        
        if event is None:
            # Race condition - quota passed but insert failed
            raise QuotaExceededError(
                usage_type=usage_type,
                used=quota_info["used"],
                limit=quota_info["limit"],
                requested=qty,
            )
        
        return event