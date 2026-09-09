"""Integration tests for the meter endpoint.

Uses direct DB inserts for bulk setup (avoids slow HTTP loops).
"""
import pytest
from httpx import AsyncClient
from src.models.tenant import Tenant
from src.models.plan import PlanTier
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.usage_event import UsageEvent, UsageType
from src.config.database import TestAsyncSessionLocal
import uuid
from datetime import datetime, timezone

pytestmark = pytest.mark.asyncio


class TestIdempotentMetering:
    """Probe 1: Same idempotency key == exactly one usage event."""

    async def test_same_idempotency_key_returns_same_event(
        self, client: AsyncClient, auth_headers: dict
    ):
        key = str(uuid.uuid4())
        
        # First request
        resp1 = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp1.status_code == 200
        event1 = resp1.json()
        
        # Second request with same key (hits Redis idempotency cache)
        resp2 = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp2.status_code == 200
        event2 = resp2.json()
        
        # Must be identical
        assert event1["usage_event_id"] == event2["usage_event_id"]
        assert event1["quantity"] == event2["quantity"]
    
    async def test_ten_retries_same_key_single_event(
        self, client: AsyncClient, auth_headers: dict, test_tenant: Tenant
    ):
        key = str(uuid.uuid4())
        
        for _ in range(10):
            resp = await client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )
            assert resp.status_code == 200
        
        # Verify exactly ONE event in database
        async with TestAsyncSessionLocal() as db:
            from sqlalchemy import select, func
            result = await db.execute(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.tenant_id == test_tenant.id,
                    UsageEvent.idempotency_key == key,
                    UsageEvent.usage_type == UsageType.API_CALL,
                )
            )
            count = result.scalar()
            assert count == 1


class TestQuotaEnforcement:
    """Probe 2: Quota boundary behavior."""
    
    async def test_exact_quota_boundary_allowed(
        self, client: AsyncClient, auth_headers: dict, test_tenant: Tenant
    ):
        """Pre-insert 4,999 events via DB, then 5,000th via HTTP should succeed."""
        now = datetime.now(timezone.utc)
        async with TestAsyncSessionLocal() as session:
            for i in range(4999):
                session.add(UsageEvent(
                    tenant_id=test_tenant.id,
                    idempotency_key=str(uuid.uuid4()),
                    usage_type=UsageType.API_CALL,
                    quantity=1,
                    cost_microunits=100,
                    created_at=now,
                ))
            await session.commit()
        
        # The 5,000th should be allowed via HTTP
        key = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp.status_code == 200
    
    async def test_over_quota_returns_429(
        self, client: AsyncClient, auth_headers: dict, test_tenant: Tenant
    ):
        """Pre-insert 10,000 events via DB, next request should be 429."""
        now = datetime.now(timezone.utc)
        async with TestAsyncSessionLocal() as session:
            for i in range(10000):
                session.add(UsageEvent(
                    tenant_id=test_tenant.id,
                    idempotency_key=str(uuid.uuid4()),
                    usage_type=UsageType.API_CALL,
                    quantity=1,
                    cost_microunits=100,
                    created_at=now,
                ))
            await session.commit()

        # Next request should be 429
        key = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp.status_code == 429
        data = resp.json()
        detail = data["detail"]
        assert detail["error"] == "quota_exceeded"
        assert "retry_after_seconds" in detail
        assert "used=10000" in detail["message"]
    
    async def test_past_due_subscription_returns_402(
        self, client: AsyncClient, auth_headers: dict, test_tenant: Tenant, async_session
    ):
        from src.repositories.subscription_repo import SubscriptionRepository
        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.PAST_DUE
        await async_session.commit()

        key = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "payment_required"

    async def test_canceled_subscription_returns_402(
        self, client: AsyncClient, auth_headers: dict, test_tenant: Tenant, async_session
    ):
        from src.repositories.subscription_repo import SubscriptionRepository
        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.CANCELED
        await async_session.commit()
        
        key = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "payment_required"
