from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class UsageDetail(BaseModel):
    model_config = {"strict": True}
    used: int = Field(..., ge=0)
    limit: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)
    cost_cents: int = Field(..., ge=0)

class TokenBreakdown(BaseModel):
    model_config= {"strict": True}
    input_tokens: int = Field(..., ge=0)
    cached_input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    reasoning_tokens: int = Field(..., ge=0)

    input_cost_cents: int = Field(..., ge=0)
    cached_input_cost_cents: int = Field(..., ge=0)
    output_cost_cents: int = Field(..., ge=0)

class UsageResponse(BaseModel):
    model_config= {"strict": True}
    period: dict[str, str]
    plan: str
    api_calls: UsageDetail
    ai_tokens: UsageDetail
    total_cost_cents: int = Field(..., ge=0)
    
