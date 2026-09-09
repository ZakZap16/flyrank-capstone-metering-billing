from pydantic import BaseModel, Field, field_validator
from src.models.usage_event import UsageType
import uuid


class MeterRequest(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}
    usage_type: UsageType = Field(..., description="Type of the usage to")
    qty: int = Field(..., gt=0, le=10_000_000, description="Quantity (should always be +ve integer)")

    @field_validator("usage_type", mode= "before")
    @classmethod
    def validate_usage_type(cls, value):
        if isinstance(value, str):
            try:
                return UsageType(value.lower())
            except ValueError:
                raise ValueError(f"Invalid usage type. It must be one of: {[e.value for e in UsageType]}")
        return value

class MeterResponse(BaseModel):
    model_config = {"strict": True}
    recorded: bool = True
    usage_event_id: uuid.UUID
    usage_type: UsageType
    quantity: int
    cost_microunits: int
    remaining_quota: dict[str, int]

class QuotaExceededError(Exception):
    
    def __init__(self, usage_type: UsageType, used: int, limit: int, requested: int):
        self.usage_type = usage_type
        self.used = used
        self.limit = limit
        self.requested = requested
        super().__init__(
            f"Quota exceeded for {usage_type.value}:"
            f"used={used}, limit={limit}, reqested={requested}"
        )

class PaymentRequiredError(Exception):

    def __init__(self, message: str = "Subscription required or Payment past due :3"):
        super().__init__(message)        
