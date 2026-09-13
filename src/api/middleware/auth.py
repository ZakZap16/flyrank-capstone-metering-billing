from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.api.deps import get_db
from src.models.tenant import Tenant
from src.services.auth_service import AuthService
from src.config.cache import cache_get, cache_set
import uuid

_TENANT_CACHE_PREFIX = "tenant:"
_TENANT_CACHE_TTL = 60


async def get_current_tenant(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    try:
        tenant_id = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Tenant-ID format"
        )

    cache_key = f"{_TENANT_CACHE_PREFIX}{tenant_id}"
    cached = await cache_get(cache_key)
    if cached:
        tenant = Tenant(**cached)
        if x_api_key and tenant.api_key_hash:
            if not AuthService.verify_api_key(x_api_key, tenant.api_key_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
        return tenant

    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found"
        )

    if x_api_key and tenant.api_key_hash:
        if not AuthService.verify_api_key(x_api_key, tenant.api_key_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )

    cache_data = {
        "id": str(tenant.id),
        "name": tenant.name,
        "email": tenant.email,
        "api_key_hash": tenant.api_key_hash,
        "stripe_customer_id": tenant.stripe_customer_id,
    }
    await cache_set(cache_key, cache_data, ttl_seconds=_TENANT_CACHE_TTL)

    return tenant
