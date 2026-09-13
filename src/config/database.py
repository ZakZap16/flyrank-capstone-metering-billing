import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

TRANSIENT_ERRORS = (
    "deadlock detected",
    "could not obtain lock",
    "connection reset",
    "connection refused",
    "server closed the connection",
    "connection timed out",
    "too many connections",
    "sorry, too many clients",
)


def is_transient_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(err in msg for err in TRANSIENT_ERRORS)


def with_db_retry(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if not is_transient_error(exc) or attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = delay * 0.1
                    wait = delay + (jitter * (attempt + 1))
                    logger.warning(
                        "db_retry attempt=%d/%d func=%s delay=%.3f error=%s",
                        attempt + 1, max_retries, func.__name__, wait, str(exc)[:100],
                    )
                    await asyncio.sleep(wait)
            raise last_exc  # type: ignore
        return wrapper
    return decorator


settings = get_settings()

engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)
