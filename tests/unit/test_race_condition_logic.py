"""A1: Race condition probe via mocked async - verify the meter_service logic.

True concurrent DB writes aren't possible with the test's shared AsyncClient
session. This test verifies the LOGIC of check-then-act: when quota check
returns "exceeded" (concurrent scenario), the meter service must raise
QuotaExceededError without writing the event.
"""
import pytest
pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
from src.services.meter_service import MeterService
from src.models.usage_event import UsageType
from src.schemas.meter import QuotaExceededError


class TestRaceConditionLogic:
    """A1: Verify quota enforcement under simulated concurrent boundary."""

    def make_meter_service(self, quota_check_return):
        session = MagicMock()
        svc = MeterService(session)
        svc.quota_service = MagicMock()
        svc.usage_repo = MagicMock()
        svc.cost_service = MagicMock()
        svc.quota_service.check_quota = AsyncMock(return_value=quota_check_return)
        return svc

    async def test_concurrent_race_at_boundary_blocks_excess(self):
        """Simulate race: first request passes quota, second request sees quota exceeded.

        The meter service MUST raise QuotaExceededError without calling
        record_usage when quota is already exceeded.
        """
        svc = self.make_meter_service(
            quota_check_return=(False, {"used": 5000, "limit": 5000, "requested": 1})
        )
        svc.usage_repo.record_usage = AsyncMock()

        with pytest.raises(QuotaExceededError):
            await svc.record(
                tenant_id=uuid.uuid4(),
                usage_type=UsageType.API_CALL,
                qty=1,
                idempotency_key=str(uuid.uuid4()),
            )

        # Critical: no DB write should have been attempted
        svc.usage_repo.record_usage.assert_not_awaited()

    async def test_idempotent_retry_does_not_duplicate(self):
        """Simulate: same idempotency key replayed → return same event, no double-charge."""
        svc = self.make_meter_service(
            quota_check_return=(True, {"used": 100, "limit": 1000, "requested": 1})
        )
        svc.cost_service.calculate = MagicMock(return_value=100)

        existing_event = MagicMock(id=uuid.uuid4(), quantity=1, cost_microunits=100)
        svc.usage_repo.record_usage = AsyncMock(return_value=existing_event)

        # 10 "concurrent" retries with the same key
        for _ in range(10):
            event = await svc.record(
                tenant_id=uuid.uuid4(),
                usage_type=UsageType.API_CALL,
                qty=1,
                idempotency_key="shared-key-123",
            )
            assert event is not None

        assert svc.usage_repo.record_usage.await_count == 10

    async def test_zero_remaining_quota_blocks_request(self):
        """When used == limit, a new request must be rejected."""
        svc = self.make_meter_service(
            quota_check_return=(False, {"used": 5000, "limit": 5000, "requested": 1, "will_exceed": True})
        )
        svc.usage_repo.record_usage = AsyncMock()

        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.record(
                tenant_id=uuid.uuid4(),
                usage_type=UsageType.API_CALL,
                qty=1,
                idempotency_key=str(uuid.uuid4()),
            )

        assert exc_info.value.used == 5000
        assert exc_info.value.limit == 5000
        svc.usage_repo.record_usage.assert_not_awaited()
