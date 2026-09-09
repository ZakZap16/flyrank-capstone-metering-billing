from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid as _uuid
from src.api.deps import get_db
from src.api.middleware.auth import get_current_tenant
from src.services.meter_service import MeterService
from src.schemas.meter import MeterRequest, MeterResponse, QuotaExceededError, PaymentRequiredError
from src.models.tenant import Tenant
from src.models.usage_event import UsageType
from src.config.cache import check_idempotency_key, store_idempotency_response

router = APIRouter(prefix="/meter", tags=["metering"])


def _cached_to_response(cached: dict) -> MeterResponse:
    if isinstance(cached.get("usage_event_id"), str):
        cached["usage_event_id"] = _uuid.UUID(cached["usage_event_id"])
    if isinstance(cached.get("usage_type"), str):
        cached["usage_type"] = UsageType(cached["usage_type"])
    return MeterResponse(**cached)


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
    cached = await check_idempotency_key(
        str(tenant.id), idempotency_key, meter_request.usage_type.value
    )
    if cached is not None:
        return _cached_to_response(cached)

    meter_service = MeterService(db)

    try:
        event, quota_info = await meter_service.record(
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

    response = MeterResponse(
        usage_event_id=event.id,
        usage_type=event.usage_type,
        quantity=event.quantity,
        cost_microunits=int(event.cost_microunits) if event.cost_microunits else 0,
        remaining_quota={
            "api_calls": int(quota_info.get("remaining", 0)) if meter_request.usage_type.value == "api_call" else 0,
            "ai_tokens": int(quota_info.get("remaining", 0)) if meter_request.usage_type.value != "api_call" else 0,
        },
    )

    await store_idempotency_response(
        str(tenant.id), idempotency_key, meter_request.usage_type.value,
        response.model_dump(mode="json"),
    )

    return response
