from sqlalchemy import String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TimestampMixin
import uuid

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    subscription: Mapped["Subscription"] = relationship(
        back_populates="tenant", uselist=False, lazy="selectin"
    )
    usage_events: Mapped[list["UsageEvent"]] = relationship(
        back_populates="tenant", lazy="dynamic"
    )
    
    __table_args__ = (
    
    )