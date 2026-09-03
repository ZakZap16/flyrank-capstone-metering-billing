from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.tenant import Tenant
import uuid

class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, name: str, api_key_hash: str) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(name=name, api_key_hash=api_key_hash)
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant