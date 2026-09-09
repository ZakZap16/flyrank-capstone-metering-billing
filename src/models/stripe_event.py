from sqlalchemy import String, DateTime, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base
from datetime import datetime
from sqlalchemy import func
from sqlalchemy import JSON


class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"
    event_id = mapped_column(String(255), primary_key=True)
    event_type = mapped_column(String(100), nullable=False)
    payload = mapped_column(JSON, nullable=False)
    processed_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    tenant_id = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    __table_args__ = (
        Index("ix_processed_stripe_events_type_time", "event_type", "processed_at"),
    )
