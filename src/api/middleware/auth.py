from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.api.deps import get_db
from src.models.tenant import Tenant
from src.services.auth_service import AuthService
import uuid

async def get_current_tenant(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Extract and validate tenant from headers.
    If X-API-Key provided, verify it against stored hash.
    """
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Tenant-ID format"
        )
    
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found"
        )
    
    # Optional: API key verification
    if x_api_key and tenant.api_key_hash:
        if not AuthService.verify_api_key(x_api_key, tenant.api_key_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
    
    return tenant