from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db
from src.api.middleware.auth import get_current_tenant
from src.repositories.tenant_repo import TenantRepository
from src.services.auth_service import AuthService
from src.schemas.auth import TenantCreate, APIKeyResponse, TenantResponse
from src.models.tenant import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post(
    "",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    plain_key, key_hash = AuthService.generate_api_key()
    
    tenant = await tenant_repo.create(
        name=tenant_data.name,
        api_key_hash=key_hash,
    )
    
    return APIKeyResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        api_key=plain_key,
    )

@router.get(
    "/me",
    response_model=TenantResponse,
)
async def get_current_tenant_info(
    tenant: Tenant = Depends(get_current_tenant),
):
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        stripe_customer_id=tenant.stripe_customer_id,
        created_at=tenant.created_at,
    )
