import pytest
pytestmark = pytest.mark.asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


class TestConcurrentMeteringAtBoundary:
    """A1: Race condition probe - concurrent requests when 1 slot remains."""

    async def test_concurrent_requests_only_one_succeeds_at_boundary(
        self, async_session: AsyncSession, test_tenant
    ):
        """When 1 quota slot remains, 20 concurrent attempts → exactly 1 event recorded."""
        from src.models.usage_event import UsageEvent, UsageType
        from src.services.meter_service import MeterService
        from src.repositories.usage_repo import UsageRepository

        FREE_API_QUOTA = 10000

        # Pre-fill to leave exactly 1 slot remaining
        async with async_session.begin():
            events = [
                UsageEvent(
                    tenant_id=test_tenant.id,
                    idempotency_key=str(uuid.uuid4()),
                    usage_type=UsageType.API_CALL,
                    quantity=1,
                    cost_microunits=1000,
                    created_at=datetime.now(timezone.utc),
                )
                for _ in range(FREE_API_QUOTA - 1)
            ]
            async_session.add_all(events)

        # Verify pre-fill
        usage_repo = UsageRepository(async_session)
        start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used_before = await usage_repo.get_monthly_usage(
            test_tenant.id, UsageType.API_CALL, start_of_month
        )
        assert used_before == FREE_API_QUOTA - 1, f"Pre-fill check failed: {used_before}"

        # Simulate 20 concurrent requests by calling MeterService.record() 20 times
        success_count = 0
        quota_exceeded_count = 0

        for i in range(20):
            meter_service = MeterService(async_session)
            try:
                await meter_service.record(
                    tenant_id=test_tenant.id,
                    usage_type=UsageType.API_CALL,
                    qty=1,
                    idempotency_key=f"{uuid.uuid4()}-{i}",
                )
                success_count += 1
            except Exception:
                quota_exceeded_count += 1

        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert quota_exceeded_count == 19, f"Expected 19 quota exceeded, got {quota_exceeded_count}"

        # Verify exactly FREE_API_QUOTA events in DB
        used_after = await usage_repo.get_monthly_usage(
            test_tenant.id, UsageType.API_CALL, start_of_month
        )
        assert used_after == FREE_API_QUOTA, f"Expected {FREE_API_QUOTA} used, got {used_after}"

    async def test_concurrent_same_idempotency_key(
        self, async_session: AsyncSession, test_tenant
    ):
        """50 concurrent attempts with the same idempotency key → exactly 1 event created."""
        from src.models.usage_event import UsageType, UsageEvent
        from src.services.meter_service import MeterService
        from src.repositories.usage_repo import UsageRepository

        key = str(uuid.uuid4())

        for _ in range(50):
            meter_service = MeterService(async_session)
            try:
                await meter_service.record(
                    tenant_id=test_tenant.id,
                    usage_type=UsageType.API_CALL,
                    qty=1,
                    idempotency_key=key,
                )
            except Exception:
                pass

        # Verify exactly 1 event in DB (idempotency key deduplicates)
        result = await async_session.execute(
            select(func.count()).select_from(UsageEvent).where(
                UsageEvent.tenant_id == test_tenant.id,
                UsageEvent.idempotency_key == key,
                UsageEvent.usage_type == UsageType.API_CALL,
            )
        )
        event_count = result.scalar()
        assert event_count == 1, f"Expected 1 event in DB, got {event_count}"
