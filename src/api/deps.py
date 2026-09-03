from sqlalchemy.ext.asyncio import AsyncSession
from src.config.database import AsyncSessionLocal

async def get_db() -> AsyncSession:
    """FastAPI dependency for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()