from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class UsageDetail(BaseModel):
    """Shows Usage for a single category (API calls or AI tokens)"""
    model_config = {"strict": True}
    used: int = Field(..., ge=0)
    limit: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)
    cost_cents: int = Field(..., ge=0)

class TokenBreakdown(BaseModel):
    """Detailed AI token usage bu category."""
    model_config= {"strict": True}
    input_tokens: int = Field(..., ge=0)
    cached_input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    reasoning_tokens: int = Field(..., ge=0)

    input_cost_cents: int = Field(..., ge=0)
    cached_input_cost_cents: int = Field(..., ge=0)
    output_cost_cents: int = Field(..., ge=0)
    reasoning_cost_cents: int = Field(..., ge=0)

class UsageResponse(BaseModel):
    """Full Usage response for current billing period"""
    model_config= {"strict": True}
    period: dict[str, str]
    plan: str
    api_calls: UsageDetail
    ai_tokens: UsageDetail
    total_cost_cents: int = Field(..., ge=0)
    