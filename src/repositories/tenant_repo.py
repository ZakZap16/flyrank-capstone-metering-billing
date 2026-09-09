from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.tenant import Tenant
import uuid

class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, name: str, email: str, api_key_hash: str, stripe_customer_id: str | None = None) -> Tenant:
        tenant = Tenant(name=name, email=email, api_key_hash=api_key_hash, stripe_customer_id=stripe_customer_id)
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant
    
    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
