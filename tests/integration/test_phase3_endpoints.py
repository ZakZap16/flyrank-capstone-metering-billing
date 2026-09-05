import pytest
import uuid
from httpx import AsyncClient
from src.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


class TestMeterValidation:
    """Test meter endpoint input validation."""

    async def test_invalid_idempotency_key_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Invalid UUID v4 for idempotency key returns 400."""
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": "not-a-uuid"},
        )
        assert resp.status_code == 400
        assert "UUID v4" in resp.json()["detail"]


class TestGetUsage:
    """Test GET /usage endpoint."""

    async def test_get_usage_returns_200(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Get current month usage for the authenticated tenant."""
        resp = await client.get("/api/v1/usage", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "api_calls" in data
        assert "ai_tokens" in data
        assert "total_cost_cents" in data


class TestSubscriptionCancel:
    """Test subscription cancel endpoint."""

    async def test_cancel_without_stripe_customer_returns_400(
        self, async_client, async_session
    ):
        """Cancel returns 400 if tenant has no Stripe customer ID."""
        from src.services.auth_service import AuthService
        from src.repositories.tenant_repo import TenantRepository

        # Create a new tenant WITHOUT a stripe_customer_id
        plain_key, key_hash = AuthService.generate_api_key()
        tenant_repo = TenantRepository(async_session)
        new_tenant = await tenant_repo.create(
            name="No Stripe Customer",
            email="no_stripe@example.com",
            api_key_hash=key_hash,
        )
        await async_session.commit()

        resp = await async_client.post(
            "/api/v1/subscriptions/cancel",
            headers={"X-Tenant-ID": str(new_tenant.id)},
        )
        assert resp.status_code == 400
        assert "Stripe customer" in resp.json()["detail"]
