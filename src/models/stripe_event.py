from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base
from datetime import datetime
from sqlalchemy import func

class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"
    
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    __table_args__ = (
        Index("ix_processed_stripe_events_type_time", "event_type", "processed_at"),
    )