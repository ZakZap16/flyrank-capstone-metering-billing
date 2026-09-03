"""Unit tests for MeterService."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from src.services.meter_service import MeterService
from src.models.usage_event import UsageType
from src.schemas.meter import QuotaExceededError, PaymentRequiredError


class TestMeterServiceRecord:
    """Test MeterService.record method."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.fixture
    def meter_service(self, mock_session):
        service = MeterService(mock_session)
        service.quota_service = MagicMock()
        service.usage_repo = MagicMock()
        service.cost_service = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_records_usage_successfully(self, meter_service):
        """Successful recording should return a UsageEvent."""
        tenant_id = uuid.uuid4()
        idempotency_key = str(uuid.uuid4())

        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 100, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4())
        )

        event = await meter_service.record(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALL,
            qty=1,
            idempotency_key=idempotency_key,
        )

        assert event is not None
        meter_service.usage_repo.record_usage.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded_when_not_allowed(self, meter_service):
        """Should raise QuotaExceededError when quota check fails."""
        tenant_id = uuid.uuid4()
        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(False, {"used": 100, "limit": 100})
        )

        with pytest.raises(QuotaExceededError):
            await meter_service.record(
                tenant_id=tenant_id,
                usage_type=UsageType.API_CALL,
                qty=1,
                idempotency_key=str(uuid.uuid4()),
            )

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded_on_race_condition(self, meter_service):
        """Should raise QuotaExceededError when record_usage returns None."""
        tenant_id = uuid.uuid4()
        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 100, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(return_value=None)

        with pytest.raises(QuotaExceededError):
            await meter_service.record(
                tenant_id=tenant_id,
                usage_type=UsageType.API_CALL,
                qty=1,
                idempotency_key=str(uuid.uuid4()),
            )

    @pytest.mark.asyncio
    async def test_passes_all_parameters_to_usage_repo(self, meter_service):
        """Should pass all parameters correctly to usage_repo."""
        tenant_id = uuid.uuid4()
        idempotency_key = str(uuid.uuid4())
        req_ip = "127.0.0.1"
        user_agent = "test-agent"

        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 0, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4())
        )

        await meter_service.record(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALL,
            qty=5,
            idempotency_key=idempotency_key,
            req_ip=req_ip,
            user_agent=user_agent,
        )

        meter_service.usage_repo.record_usage.assert_awaited_once_with(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            usage_type=UsageType.API_CALL,
            quantity=5,
            cost_microunits=100,
            request_ip=req_ip,
            user_agent=user_agent,
        )

    @pytest.mark.asyncio
    async def test_different_usage_types(self, meter_service):
        """Should work with different usage types."""
        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 0, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4())
        )

        event = await meter_service.record(
            tenant_id=uuid.uuid4(),
            usage_type=UsageType.INPUT_TOKENS,
            qty=1000,
            idempotency_key=str(uuid.uuid4()),
        )

        assert event is not None

    @pytest.mark.asyncio
    async def test_passes_req_ip_and_user_agent(self, meter_service):
        """req_ip and user_agent should be passed to record_usage."""
        tenant_id = uuid.uuid4()

        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 0, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4())
        )

        await meter_service.record(
            tenant_id=tenant_id,
            usage_type=UsageType.API_CALL,
            qty=1,
            idempotency_key=str(uuid.uuid4()),
            req_ip="192.168.1.1",
            user_agent="curl/7.0",
        )

        call_kwargs = meter_service.usage_repo.record_usage.call_args.kwargs
        assert call_kwargs["request_ip"] == "192.168.1.1"
        assert call_kwargs["user_agent"] == "curl/7.0"

    @pytest.mark.asyncio
    async def test_req_ip_and_user_agent_none_by_default(self, meter_service):
        """req_ip and user_agent should default to None."""
        meter_service.quota_service.check_quota = AsyncMock(
            return_value=(True, {"used": 0, "limit": 1000})
        )
        meter_service.cost_service.calculate = MagicMock(return_value=100)
        meter_service.usage_repo.record_usage = AsyncMock(
            return_value=MagicMock(id=uuid.uuid4())
        )

        await meter_service.record(
            tenant_id=uuid.uuid4(),
            usage_type=UsageType.API_CALL,
            qty=1,
            idempotency_key=str(uuid.uuid4()),
        )

        call_kwargs = meter_service.usage_repo.record_usage.call_args.kwargs
        assert call_kwargs["request_ip"] is None
        assert call_kwargs["user_agent"] is None