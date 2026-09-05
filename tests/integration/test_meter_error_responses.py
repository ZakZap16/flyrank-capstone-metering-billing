import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from src.schemas.meter import QuotaExceededError, PaymentRequiredError
from src.models.usage_event import UsageType

pytestmark = pytest.mark.asyncio


class TestMeterErrorResponses:
    """Test meter endpoint error response structures (lines 48-76)."""

    async def test_quota_exceeded_response_structure(self, async_client, test_tenant, auth_headers):
        """QuotaExceededError handler returns correct 429 structure."""
        with patch("src.services.meter_service.MeterService.record") as mock_record:
            mock_record.side_effect = QuotaExceededError(
                usage_type=UsageType.API_CALL,
                used=10000,
                limit=10000,
                requested=1,
            )

            key = str(uuid.uuid4())
            resp = await async_client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )

            assert resp.status_code == 429
            detail = resp.json()["detail"]
            assert detail["error"] == "quota_exceeded"
            assert "retry_after_seconds" in detail
            assert "Retry-After" in resp.headers

    async def test_payment_required_response_structure(self, async_client, test_tenant, auth_headers):
        """PaymentRequiredError handler returns correct 402 structure."""
        with patch("src.services.meter_service.MeterService.record") as mock_record:
            mock_record.side_effect = PaymentRequiredError(
                message="Subscription is past due. Please update payment method."
            )

            key = str(uuid.uuid4())
            resp = await async_client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )

            assert resp.status_code == 402
            detail = resp.json()["detail"]
            assert detail["error"] == "payment_required"

    async def test_success_response_structure(self, async_client, test_tenant, auth_headers):
        """Success response returns correct MeterResponse structure."""
        with patch("src.services.meter_service.MeterService.record") as mock_record, \
             patch("src.services.quota_service.QuotaService.get_all_quotas", new_callable=AsyncMock) as mock_quotas:

            mock_event = MagicMock()
            mock_event.id = uuid.uuid4()
            mock_event.usage_type = UsageType.API_CALL
            mock_event.quantity = 1
            mock_event.cost_microunits = 100
            mock_record.return_value = mock_event

            mock_quotas.return_value = {
                "plan": "pro",
                "api_calls": {"used": 5, "limit": 50000, "remaining": 49995},
                "ai_tokens": {"used": 100, "limit": 5000000, "remaining": 4999900},
            }

            key = str(uuid.uuid4())
            resp = await async_client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "usage_event_id" in data
            assert data["usage_type"] == "api_call"
            assert data["quantity"] == 1
            assert data["cost_microunits"] == 100
            assert "remaining_quota" in data
            assert data["remaining_quota"]["api_calls"] == 49995
            assert data["remaining_quota"]["ai_tokens"] == 4999900

    async def test_success_response_cost_microunits_none(self, async_client, test_tenant, auth_headers):
        """MeterResponse handles cost_microunits=None gracefully."""
        with patch("src.services.meter_service.MeterService.record") as mock_record, \
             patch("src.services.quota_service.QuotaService.get_all_quotas", new_callable=AsyncMock) as mock_quotas:

            mock_event = MagicMock()
            mock_event.id = uuid.uuid4()
            mock_event.usage_type = UsageType.API_CALL
            mock_event.quantity = 1
            mock_event.cost_microunits = None
            mock_record.return_value = mock_event

            mock_quotas.return_value = {
                "plan": "free",
                "api_calls": {"used": 0, "limit": 10000, "remaining": 10000},
                "ai_tokens": {"used": 0, "limit": 100000, "remaining": 100000},
            }

            key = str(uuid.uuid4())
            resp = await async_client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )

            assert resp.status_code == 200
            assert resp.json()["cost_microunits"] == 0
