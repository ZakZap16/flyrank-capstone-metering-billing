from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db
from src.api.middleware.auth import get_current_tenant
from src.services.meter_service import MeterService
from src.schemas.meter import MeterRequest, MeterResponse, QuotaExceededError, PaymentRequiredError
from src.models.tenant import Tenant

router = APIRouter(prefix="/meter", tags=["metering"])

@router.post(
    "",
    response_model=MeterResponse,
    status_code=status.HTTP_200_OK,
    responses={
        402: {"description": "Payment required - subscription issue"},
        429: {"description": "Quota exceeded"},
        401: {"description": "Invalid tenant"},
        400: {"description": "Invalid request"},
    },
)
async def record_usage(
    request: Request,
    meter_request: MeterRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a billable usage event.

    **Idempotency**: Same `Idempotency-Key` + `usage_type` + `tenant`
    returns the original event without double-counting.

    **Quota**: Enforced before recording. Returns 429 if exceeded.
    """
    meter_service = MeterService(db)

    try:
        event = await meter_service.record(
            tenant_id=tenant.id,
            usage_type=meter_request.usage_type,
            qty=meter_request.qty,
            idempotency_key=idempotency_key,
            req_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message": str(exc),
                "usage_type": exc.usage_type.value,
                "used": exc.used,
                "limit": exc.limit,
                "requested": exc.requested,
                "retry_after_seconds": 86400,
            },
            headers={"Retry-After": "86400"},
        )
    except PaymentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "payment_required",
                "message": str(exc),
            },
        )

    from src.services.quota_service import QuotaService
    quota_service = QuotaService(db)
    quotas = await quota_service.get_all_quotas(tenant.id)

    return MeterResponse(
        usage_event_id=event.id,
        usage_type=event.usage_type,
        quantity=event.quantity,
        cost_microunits=int(event.cost_microunits) if event.cost_microunits else 0,
        remaining_quota={
            "api_calls": int(quotas.get("api_calls", {}).get("remaining", 0)),
            "ai_tokens": int(quotas.get("ai_tokens", {}).get("remaining", 0)),
        },
    )