import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from src.main import create_app
from src.models.base import Base
from src.config.settings import get_settings
from src.repositories.tenant_repo import TenantRepository
from src.repositories.subscription_repo import SubscriptionRepository
from src.repositories.plan_repo import PlanRepository
from src.services.auth_service import AuthService
from src.models.tenant import Tenant
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.plan import PlanTier
from datetime import datetime, timezone
import uuid
from dateutil.relativedelta import relativedelta

settings = get_settings()

# Test database engine (separate from dev)
TEST_DATABASE_URL = str(settings.DATABASE_URL).replace(
    "metering_billing", "metering_billing_test"
)


@pytest_asyncio.fixture
async def async_session():
    """Create a fresh session with a fresh transaction per test."""
    from sqlalchemy import text, event

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        from src.models.plan import Plan

        plans = {
            PlanTier.FREE: {
                "name": "Free",
                "api_call_quota": 10000,
                "ai_token_quota": 100_000,
                "price_cents": 0,
                "stripe_price_id": None,
            },
            PlanTier.PRO: {
                "name": "Pro",
                "api_call_quota": 50_000,
                "ai_token_quota": 5_000_000,
                "price_cents": 5000,
                "stripe_price_id": "price_pro",
            },
        }

        for plan_id, config in plans.items():
            session.add(Plan(
                id=plan_id,
                name=config["name"],
                api_call_quota=config["api_call_quota"],
                ai_token_quota=config["ai_token_quota"],
                price_cents=config["price_cents"],
                stripe_price_id=config["stripe_price_id"],
                is_active=True,
            ))
        await session.commit()
        yield session
        await session.close()


@pytest_asyncio.fixture
async def client(async_session):
    """Alias for async_client."""
    from src.api.deps import get_db

    app = create_app()

    async def override_get_db():
        try:
            yield async_session
            await async_session.flush()
            await async_session.commit()
        except Exception:
            await async_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(async_session):
    """AsyncClient with overridden database dependency."""
    from src.api.deps import get_db

    app = create_app()

    async def override_get_db():
        try:
            yield async_session
            await async_session.flush()
            await async_session.commit()
        except Exception:
            await async_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_tenant(async_session):
    """Create a test tenant with Free plan subscription."""
    tenant_repo = TenantRepository(async_session)
    sub_repo = SubscriptionRepository(async_session)
    plan_repo = PlanRepository(async_session)

    plain_key, key_hash = AuthService.generate_api_key()
    tenant = await tenant_repo.create(
        name="Test Tenant",
        email="test@example.com",
        api_key_hash=key_hash,
        stripe_customer_id="cus_test_123",
    )
    await async_session.commit()

    free_plan = await plan_repo.get_by_id(PlanTier.FREE)

    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=PlanTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + relativedelta(years=1),
    )
    async_session.add(subscription)
    await async_session.commit()

    return tenant


@pytest_asyncio.fixture
def auth_headers(test_tenant):
    """Headers for authenticated requests."""
    return {"X-Tenant-ID": str(test_tenant.id)}