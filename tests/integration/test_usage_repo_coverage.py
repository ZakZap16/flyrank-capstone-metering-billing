import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
from src.models.usage_event import UsageEvent, UsageType
from src.repositories.usage_repo import UsageRepository
from src.services.auth_service import AuthService
from src.repositories.tenant_repo import TenantRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def usage_tenant(async_session):
    """Create a fresh tenant with a FREE plan subscription for usage repo tests."""
    from src.models.subscription import Subscription, SubscriptionStatus
    from src.models.plan import PlanTier
    from src.repositories.subscription_repo import SubscriptionRepository

    tenant_repo = TenantRepository(async_session)
    plain_key, key_hash = AuthService.generate_api_key()
    tenant = await tenant_repo.create(
        name="Usage Repo Test",
        email=f"usage_{uuid.uuid4()}@example.com",
        api_key_hash=key_hash,
    )
    await async_session.flush()

    sub_repo = SubscriptionRepository(async_session)
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=PlanTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1),
    )
    async_session.add(sub)
    await async_session.commit()
    await async_session.refresh(tenant)
    return tenant


class TestUsageRepository:
    """Unit tests for UsageRepository uncovered methods."""

    async def test_get_monthly_cost_no_events(self, async_session, usage_tenant):
        """get_monthly_cost returns 0 when no events exist."""
        repo = UsageRepository(async_session)
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cost = await repo.get_monthly_cost(usage_tenant.id, start)
        assert cost == 0

    async def test_get_monthly_cost_with_events(self, async_session, usage_tenant):
        """get_monthly_cost sums cost_microunits for the current month."""
        now = datetime.now(timezone.utc)
        for i in range(3):
            async_session.add(UsageEvent(
                tenant_id=usage_tenant.id,
                idempotency_key=str(uuid.uuid4()),
                usage_type=UsageType.API_CALL,
                quantity=1,
                cost_microunits=100 * (i + 1),
                created_at=now,
            ))
        await async_session.commit()

        repo = UsageRepository(async_session)
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cost = await repo.get_monthly_cost(usage_tenant.id, start)
        assert cost == 100 + 200 + 300  # 600

    async def test_get_monthly_cost_excludes_prior_month(self, async_session, usage_tenant):
        """get_monthly_cost excludes events before start_of_month."""
        from datetime import timedelta
        last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
        this_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        async_session.add(UsageEvent(
            tenant_id=usage_tenant.id,
            idempotency_key=str(uuid.uuid4()),
            usage_type=UsageType.API_CALL,
            quantity=1,
            cost_microunits=9999,
            created_at=last_month,
        ))
        async_session.add(UsageEvent(
            tenant_id=usage_tenant.id,
            idempotency_key=str(uuid.uuid4()),
            usage_type=UsageType.API_CALL,
            quantity=1,
            cost_microunits=100,
            created_at=this_month + timedelta(hours=1),
        ))
        await async_session.commit()

        repo = UsageRepository(async_session)
        cost = await repo.get_monthly_cost(usage_tenant.id, this_month)
        assert cost == 100  # Excludes the 9999 from last month

    async def test_record_idempotency_conflict(self, async_session, usage_tenant):
        """record() returns the existing event on idempotency conflict (lines 40-55)."""
        from src.services.meter_service import MeterService

        key = str(uuid.uuid4())
        svc = MeterService(async_session)
        event1 = await svc.record(
            tenant_id=usage_tenant.id,
            usage_type=UsageType.API_CALL,
            qty=1,
            idempotency_key=key,
            req_ip="127.0.0.1",
            user_agent="test",
        )
        await async_session.commit()

        # Second call with same key+usage_type returns same event
        event2 = await svc.record(
            tenant_id=usage_tenant.id,
            usage_type=UsageType.API_CALL,
            qty=1,
            idempotency_key=key,
            req_ip="127.0.0.1",
            user_agent="test",
        )
        await async_session.commit()

        assert event1.id == event2.id
        assert event1.quantity == event2.quantity
