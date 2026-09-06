from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from src.api.deps import get_db
from src.api.middleware.auth import get_current_tenant
from src.services.quota_service import QuotaService
from src.services.cost_service import CostService
from src.repositories.usage_repo import UsageRepository
from src.models.tenant import Tenant
from src.models.usage_event import UsageType
from src.utils.money import microunits_to_cents
from src.schemas.usage import UsageResponse, UsageDetail, TokenBreakdown

router = APIRouter(prefix="/usage", tags=["usage"])

@router.get("", response_model=UsageResponse)
async def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get current month usage, limits, and costs for the tenant."""
    quota_service = QuotaService(db)
    usage_repo = UsageRepository(db)
    cost_service = CostService()

    quotas = await quota_service.get_all_quotas(tenant.id)
    if "error" in quotas:
        raise HTTPException(status_code=404, detail=quotas["error"])

    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_cost_microunits = await usage_repo.get_monthly_cost(tenant.id, start_of_month)
    usage_breakdown = await usage_repo.get_monthly_usage_breakdown(tenant.id, start_of_month)

    # Calculate token cost breakdown using billing rules engine
    token_breakdown = cost_service.calculate_token_breakdown(
        input_tokens=usage_breakdown.get(UsageType.INPUT_TOKENS, 0),
        cached_input_tokens=usage_breakdown.get(UsageType.CACHED_INPUT_TOKENS, 0),
        output_tokens=usage_breakdown.get(UsageType.OUTPUT_TOKENS, 0),
        reasoning_tokens=usage_breakdown.get(UsageType.REASONING_TOKENS, 0),
    )

    return UsageResponse(
        period={
            "start": start_of_month.isoformat(),
            "end": (start_of_month.replace(month=start_of_month.month + 1) if start_of_month.month < 12
                   else start_of_month.replace(year=start_of_month.year + 1, month=1)).isoformat(),
        },
        plan=quotas["plan"],
        api_calls=UsageDetail(
            used=quotas["api_calls"]["used"],
            limit=quotas["api_calls"]["limit"],
            remaining=quotas["api_calls"]["remaining"],
            cost_cents=microunits_to_cents(
                CostService().calculate(UsageType.API_CALL, quotas["api_calls"]["used"])
            ),
        ),
        ai_tokens=UsageDetail(
            used=quotas["ai_tokens"]["used"],
            limit=quotas["ai_tokens"]["limit"],
            remaining=quotas["ai_tokens"]["remaining"],
            cost_cents=microunits_to_cents(sum(token_breakdown.values())),
            breakdown=TokenBreakdown(
                input_tokens=usage_breakdown.get(UsageType.INPUT_TOKENS, 0),
                cached_input_tokens=usage_breakdown.get(UsageType.CACHED_INPUT_TOKENS, 0),
                output_tokens=usage_breakdown.get(UsageType.OUTPUT_TOKENS, 0),
                reasoning_tokens=usage_breakdown.get(UsageType.REASONING_TOKENS, 0),
                input_cost_cents=microunits_to_cents(token_breakdown["input_tokens"]),
                cached_input_cost_cents=microunits_to_cents(token_breakdown["cached_input_tokens"]),
                output_cost_cents=microunits_to_cents(token_breakdown["output_tokens"]),
                reasoning_cost_cents=microunits_to_cents(token_breakdown["reasoning_tokens"]),
            ),
        ),
        total_cost_cents=microunits_to_cents(total_cost_microunits),
    )