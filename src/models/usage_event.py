from sqlalchemy import String, BigInteger, ForeignKey, UniqueConstraint, Index, Enum as SQLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base
from src.models.tenant import Tenant
import enum
import uuid

class UsageType(str, enum.Enum):
    API_CALL = "api_call"
    INPUT_TOKENS = "input_tokens"
    CACHED_INPUT_TOKENS = "cached_input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    REASONING_TOKENS = "reasoning_tokens"

class UsageEvent(Base):
    __tablename__ = "usage_events"
    
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    usage_type: Mapped[UsageType] = mapped_column(
        SQLEnum(UsageType, native_enum=False), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_microunits: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    request_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    tenant: Mapped[Tenant] = relationship(back_populates="usage_events", lazy="selectin")
    
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", "usage_type",
            name="uq_tenant_idempotency_usage_type"
        ),
        Index("ix_usage_events_tenant_month", "tenant_id", "created_at"),
        Index("ix_usage_events_tenant_type_month", "tenant_id", "usage_type", "created_at"),
    )
