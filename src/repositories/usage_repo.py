from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.models.usage_event import UsageEvent, UsageType
from src.models.tenant import Tenant
from datetime import datetime, timezone
import uuid

class UsageRepository:
    def __init__(self, session: AsyncSession):
        self.session =session
    
    async def record_usage(
        self,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        usage_type: UsageType,
        quantity: int,
        cost_microunits: int,
        request_ip: str | None = None,
        user_agent: str | None = None,
    ) -> UsageEvent | None:
        """
        Atomically record usage event with idempotency.
        Returns existing event if duplicate key, None if quota would be exceeded.
        """
        stmt = pg_insert(UsageEvent).values(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            usage_type=usage_type,
            quantity=quantity,
            cost_microunits=cost_microunits,
            request_ip=request_ip,
            user_agent=user_agent,
        ).on_conflict_do_nothing(
            index_elements=["tenant_id", "idempotency_key", "usage_type"]
        ).returning(UsageEvent)
        
        result = await self.session.execute(stmt)
        event = result.scalar_one_or_none()
        
        if event:
            return event
        
        # Conflict occurred - fetch existing
        existing = await self.session.execute(
            select(UsageEvent).where(
                and_(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.idempotency_key == idempotency_key,
                    UsageEvent.usage_type == usage_type,
                )
            )
        )
        return existing.scalar_one_or_none()
    
    async def get_monthly_usage(
        self, tenant_id: uuid.UUID, usage_type: UsageType, start_of_month: datetime
    ) -> int:
        """Get total usage for a tenant/type in current month."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                and_(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.usage_type == usage_type,
                    UsageEvent.created_at >= start_of_month,
                )
            )
        )
        return int(result.scalar_one())
    
    async def get_monthly_usage_breakdown(
        self, tenant_id: uuid.UUID, start_of_month: datetime
    ) -> dict[UsageType, int]:
        """Get usage breakdown by type for current month."""
        result = await self.session.execute(
            select(UsageEvent.usage_type, func.coalesce(func.sum(UsageEvent.quantity), 0))
            .where(
                and_(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.created_at >= start_of_month,
                )
            )
            .group_by(UsageEvent.usage_type)
        )
        return {row.usage_type: int(row[1]) for row in result.all()}
    
    async def get_monthly_cost(self, tenant_id: uuid.UUID, start_of_month: datetime) -> int:
        """Get total cost in micro-units for current month."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(UsageEvent.cost_microunits), 0)).where(
                and_(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.created_at >= start_of_month,
                )
            )
        )
        return result.scalar_one()