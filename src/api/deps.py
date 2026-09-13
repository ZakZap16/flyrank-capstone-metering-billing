from sqlalchemy.ext.asyncio import AsyncSession
from src.config.database import AsyncSessionLocal
from src.services.stripe_service import StripeService

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_stripe_service() -> StripeService:
    return StripeService()
