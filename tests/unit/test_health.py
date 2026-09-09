import pytest
pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from src.main import create_app


@pytest.fixture
def app():
    return create_app()


class TestHealthCheck:
    async def test_health_returns_200(self, app, async_session):
        from src.api.deps import get_db
        app.dependency_overrides[get_db] = lambda: async_session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    async def test_health_returns_503_on_db_error(self, app):
        from src.api.deps import get_db
        bad_session = AsyncMock()
        bad_session.execute = AsyncMock(side_effect=Exception("connection refused"))
        app.dependency_overrides[get_db] = lambda: bad_session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 503


class TestReadinessCheck:
    async def test_ready_returns_200_when_all_healthy(self, app, async_session):
        from src.api.deps import get_db
        from src.api.health import get_stripe_service
        app.dependency_overrides[get_db] = lambda: async_session
        mock_stripe = AsyncMock()
        mock_stripe.get_customer = AsyncMock(return_value=MagicMock())
        app.dependency_overrides[get_stripe_service] = lambda: mock_stripe
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ready"
        assert data["checks"]["stripe"] == "ready"

    async def test_ready_returns_503_when_db_fails(self, app):
        from src.api.deps import get_db
        from src.api.health import get_stripe_service
        bad_session = AsyncMock()
        bad_session.execute = AsyncMock(side_effect=Exception("db down"))
        app.dependency_overrides[get_db] = lambda: bad_session
        mock_stripe = AsyncMock()
        mock_stripe.get_customer = AsyncMock(return_value=MagicMock())
        app.dependency_overrides[get_stripe_service] = lambda: mock_stripe
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["database"] == "not_ready"

    async def test_ready_returns_503_when_stripe_fails(self, app, async_session):
        from src.api.deps import get_db
        from src.api.health import get_stripe_service
        app.dependency_overrides[get_db] = lambda: async_session
        mock_stripe = AsyncMock()
        mock_stripe.get_customer = AsyncMock(side_effect=Exception("stripe down"))
        app.dependency_overrides[get_stripe_service] = lambda: mock_stripe
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["stripe"] == "not_ready"
