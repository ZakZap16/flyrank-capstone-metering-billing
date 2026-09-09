from src.repositories.usage_repo import UsageRepository
from src.services.quota_service import QuotaService
from src.services.cost_service import CostService
from src.models.usage_event import UsageType, UsageEvent
from src.schemas.meter import QuotaExceededError, PaymentRequiredError
from src.config.database import with_db_retry
from datetime import datetime, timezone

import uuid

class MeterService:
    def __init__(self, session):
        self.usage_repo = UsageRepository(session)
        self.quota_service = QuotaService(session)
        self.cost_service = CostService()
    
    @with_db_retry(max_retries=3, base_delay=0.05, max_delay=0.5)
    async def record(
        self,
        tenant_id: uuid.UUID,
        usage_type: UsageType,
        qty: int,
        idempotency_key: str,
        req_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[UsageEvent, dict]:
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
        
        cost_microunits = self.cost_service.calculate(usage_type, qty)
        
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
            raise QuotaExceededError(
                usage_type=usage_type,
                used=quota_info["used"],
                limit=quota_info["limit"],
                requested=qty,
            )
        
        updated_quota_info = {
            "usage_type": usage_type.value,
            "used": quota_info["used"] + qty,
            "limit": quota_info["limit"],
            "remaining": max(0, quota_info["limit"] - (quota_info["used"] + qty)),
        }
        
        return event, updated_quota_info
