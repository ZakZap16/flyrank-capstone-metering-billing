from pydantic import BaseModel, ConfigDict
from typing import Literal


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"plan_tier": "pro"}}
    )
    
    plan_tier: Literal["free", "pro"]
