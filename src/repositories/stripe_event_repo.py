from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.stripe_event import ProcessedStripeEvent
from uuid import UUID

class StripeEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def is_processed(self, event_id: str) -> bool:
        """Check if we've already processed this Stripe event"""
        query = select(ProcessedStripeEvent).where(ProcessedStripeEvent.event_id == event_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def mark_processed(
        self, 
        event_id: str, 
        event_type: str, 
        payload: dict, 
        tenant_id: UUID | None = None
    ) -> ProcessedStripeEvent:
        """Record that we've processed a Stripe event"""
        db_event = ProcessedStripeEvent(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            tenant_id=tenant_id
        )
        self.session.add(db_event)
        await self.session.commit()
        await self.session.refresh(db_event)
        return db_event