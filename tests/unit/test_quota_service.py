"""Unit tests for QuotaService."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime, timezone

from src.services.quota_service import QuotaService
from src.models.usage_event import UsageType
from src.models.subscription import SubscriptionStatus
from src.models.plan import PlanTier
from src.schemas.meter import PaymentRequiredError


class MockSubscription:
    def __init__(self, plan_id=PlanTier.FREE, status=SubscriptionStatus.ACTIVE):
        self.plan_id = plan_id
        self.status = status


class MockPlan:
    def __init__(self, api_call_quota=10000, ai_token_quota=100000):
        self.api_call_quota = api_call_quota
        self.ai_token_quota = ai_token_quota
        self.name = "Test Plan"


class TestQuotaServiceCheckQuota:
    """Test QuotaService.check_quota method."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.fixture
    def quota_service(self, mock_session):
        service = QuotaService(mock_session)
        # Mock the repos
        service.subscription_repo = MagicMock()
        service.plan_repo = MagicMock()
        service.usage_repo = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_allows_request_within_quota(self, quota_service):
        """Request within quota should be allowed."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=10000)
        )
        quota_service.usage_repo.get_monthly_usage = AsyncMock(return_value=5000)

        allowed, info = await quota_service.check_quota(
            tenant_id, UsageType.API_CALL, 1000
        )

        assert allowed is True
        assert info["limit"] == 10000
        assert info["used"] == 5000
        assert info["requested"] == 1000
        assert info["will_exceed"] is False

    @pytest.mark.asyncio
    async def test_blocks_request_exceeding_quota(self, quota_service):
        """Request exceeding quota should be blocked."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=10000)
        )
        quota_service.usage_repo.get_monthly_usage = AsyncMock(return_value=9900)

        allowed, info = await quota_service.check_quota(
            tenant_id, UsageType.API_CALL, 200
        )

        assert allowed is False
        assert info["will_exceed"] is True

    @pytest.mark.asyncio
    async def test_raises_payment_required_when_no_subscription(self, quota_service):
        """No active subscription should raise PaymentRequiredError."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(return_value=None)

        with pytest.raises(PaymentRequiredError) as exc_info:
            await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert "No active subscription found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_payment_required_when_past_due(self, quota_service):
        """Past due subscription should raise PaymentRequiredError."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription(status=SubscriptionStatus.PAST_DUE)
        )

        with pytest.raises(PaymentRequiredError) as exc_info:
            await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert "past due" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_payment_required_when_canceled(self, quota_service):
        """Canceled subscription should raise PaymentRequiredError."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription(status=SubscriptionStatus.CANCELED)
        )

        with pytest.raises(PaymentRequiredError) as exc_info:
            await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert "canceled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_payment_required_when_plan_not_found(self, quota_service):
        """Plan not found should raise PaymentRequiredError."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(PaymentRequiredError) as exc_info:
            await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert "Plan not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uses_api_call_quota_for_api_calls(self, quota_service):
        """API_CALL usage should use api_call_quota."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=5000, ai_token_quota=100000)
        )
        quota_service.usage_repo.get_monthly_usage = AsyncMock(return_value=0)

        _, info = await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert info["limit"] == 5000

    @pytest.mark.asyncio
    async def test_uses_token_quota_for_tokens(self, quota_service):
        """Token usage types should use ai_token_quota."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=10000, ai_token_quota=50000)
        )
        quota_service.usage_repo.get_monthly_usage = AsyncMock(return_value=0)

        _, info = await quota_service.check_quota(tenant_id, UsageType.INPUT_TOKENS, 1)

        assert info["limit"] == 50000

    @pytest.mark.asyncio
    async def test_remaining_calculation(self, quota_service):
        """Remaining should be max(0, limit - used)."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=10000)
        )
        quota_service.usage_repo.get_monthly_usage = AsyncMock(return_value=7500)

        _, info = await quota_service.check_quota(tenant_id, UsageType.API_CALL, 1)

        assert info["remaining"] == 2500


class TestQuotaServiceGetAllQuotas:
    """Test QuotaService.get_all_quotas method."""

    @pytest.fixture
    def quota_service(self):
        session = MagicMock()
        service = QuotaService(session)
        service.subscription_repo = MagicMock()
        service.plan_repo = MagicMock()
        service.usage_repo = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_returns_error_when_no_subscription(self, quota_service):
        """No subscription should return error dict."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(return_value=None)

        result = await quota_service.get_all_quotas(tenant_id)

        assert "error" in result
        assert "No active subscription" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_plan_not_found(self, quota_service):
        """Plan not found should return error dict."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(return_value=None)

        result = await quota_service.get_all_quotas(tenant_id)

        assert "error" in result
        assert "Plan not found" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_full_quota_breakdown(self, quota_service):
        """Should return full quota breakdown with api_calls and ai_tokens."""
        tenant_id = uuid.uuid4()
        quota_service.subscription_repo.get_active_by_tenant = AsyncMock(
            return_value=MockSubscription()
        )
        quota_service.plan_repo.get_by_id = AsyncMock(
            return_value=MockPlan(api_call_quota=10000, ai_token_quota=100000)
        )
        quota_service.usage_repo.get_monthly_usage_breakdown = AsyncMock(
            return_value={UsageType.API_CALL: 5000, UsageType.INPUT_TOKENS: 20000}
        )

        result = await quota_service.get_all_quotas(tenant_id)

        assert "plan" in result
        assert "api_calls" in result
        assert "ai_tokens" in result
        assert result["api_calls"]["limit"] == 10000
        assert result["api_calls"]["used"] == 5000
        assert result["api_calls"]["remaining"] == 5000