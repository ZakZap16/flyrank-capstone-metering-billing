from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.plan import Plan, PlanTier

class PlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, plan_tier: PlanTier) -> Plan | None:
        stmt = select(Plan).where(Plan.id == plan_tier)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
