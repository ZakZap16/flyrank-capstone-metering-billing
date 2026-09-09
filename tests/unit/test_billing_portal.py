import pytest
pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from src.main import create_app


@pytest.fixture
def app():
    return create_app()


class TestBillingPortal:
    async def test_portal_returns_url(self, app, async_session, test_tenant):
        from src.api.deps import get_db
        from src.api.middleware.auth import get_current_tenant
        from src.api.v1.billing import get_stripe_service
        app.dependency_overrides[get_db] = lambda: async_session
        app.dependency_overrides[get_current_tenant] = lambda: test_tenant
        mock_stripe = AsyncMock()
        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/session/test"
        mock_stripe.create_portal_session = AsyncMock(return_value=mock_portal)
        app.dependency_overrides[get_stripe_service] = lambda: mock_stripe
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/billing/portal",
                headers={"X-Tenant-ID": str(test_tenant.id)}
            )
        assert resp.status_code == 200
        assert "url" in resp.json()

    async def test_portal_no_stripe_customer_returns_400(self, app, async_session, test_tenant):
        from src.api.deps import get_db
        from src.api.middleware.auth import get_current_tenant
        app.dependency_overrides[get_db] = lambda: async_session
        tenant_no_stripe = MagicMock()
        tenant_no_stripe.id = test_tenant.id
        tenant_no_stripe.stripe_customer_id = None
        app.dependency_overrides[get_current_tenant] = lambda: tenant_no_stripe
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/billing/portal",
                headers={"X-Tenant-ID": str(test_tenant.id)}
            )
        assert resp.status_code == 400
