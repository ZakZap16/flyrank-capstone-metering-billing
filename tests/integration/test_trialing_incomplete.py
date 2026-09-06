"""A6: TRIALING/INCOMPLETE subscription should allow metering per business decision."""
import pytest
pytestmark = pytest.mark.asyncio
import uuid
from httpx import AsyncClient


class TestTrialingIncompleteAllowMetering:
    """A6: TRIALING and INCOMPLETE statuses should allow metering (not raise 402)."""

    async def test_trialing_subscription_allows_metering(
        self, client: AsyncClient, auth_headers: dict, test_tenant, async_session
    ):
        """A trialing subscription should not block usage recording."""
        from src.repositories.subscription_repo import SubscriptionRepository
        from src.models.subscription import SubscriptionStatus

        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.TRIALING
        await async_session.commit()

        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage_event_id"] is not None
        assert data["quantity"] == 1

    async def test_incomplete_subscription_allows_metering(
        self, client: AsyncClient, auth_headers: dict, test_tenant, async_session
    ):
        """An incomplete subscription should not block usage recording."""
        from src.repositories.subscription_repo import SubscriptionRepository
        from src.models.subscription import SubscriptionStatus

        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.INCOMPLETE
        await async_session.commit()

        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 200

    async def test_past_due_subscription_still_blocks_metering(
        self, client: AsyncClient, auth_headers: dict, test_tenant, async_session
    ):
        """Sanity check: past_due still blocks metering (existing behavior preserved)."""
        from src.repositories.subscription_repo import SubscriptionRepository
        from src.models.subscription import SubscriptionStatus

        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.PAST_DUE
        await async_session.commit()

        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "payment_required"

    async def test_canceled_subscription_still_blocks_metering(
        self, client: AsyncClient, auth_headers: dict, test_tenant, async_session
    ):
        """Sanity check: canceled still blocks metering."""
        from src.repositories.subscription_repo import SubscriptionRepository
        from src.models.subscription import SubscriptionStatus

        sub_repo = SubscriptionRepository(async_session)
        sub = await sub_repo.get_active_by_tenant(test_tenant.id)
        sub.status = SubscriptionStatus.CANCELED
        await async_session.commit()

        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 402
