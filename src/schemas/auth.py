from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TenantCreate(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}
    name: str = Field(..., min_length=1, max_length=255)

class APIKeyResponse(BaseModel):
    model_config = {"strict": True}
    tenant_id: str
    name: str
    api_key: str

class TenantResponse(BaseModel):
    model_config = {"strict": True}
    id: str
    name: str
    stripe_customer_id: Optional[str] = None
    created_at: datetime
