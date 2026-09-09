from sqlalchemy import String, DateTime, ForeignKey, Enum as SQLEnum, Index, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from src.models.base import Base, TimestampMixin
from src.models.plan import PlanTier
from src.models.tenant import Tenant
import enum

import uuid

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"

class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    plan_id: Mapped[PlanTier] = mapped_column(
        ForeignKey("plans.id"), nullable=False, default=PlanTier.FREE
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, native_enum=False), nullable=False, default=SubscriptionStatus.INCOMPLETE
    )
    current_period_start: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False, nullable=False)
    canceled_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    tenant: Mapped[Tenant] = relationship(back_populates="subscription", lazy="selectin")
    plan: Mapped["Plan"] = relationship(lazy="selectin")
    
    __table_args__ = (
        Index("ix_subscriptions_stripe_id", "stripe_subscription_id"),
        Index("ix_subscriptions_status", "status"),
    )
