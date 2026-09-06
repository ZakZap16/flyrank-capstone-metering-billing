"""A1: Concurrent requests at quota boundary - only 1 should succeed when 1 slot remains."""
import pytest
pytestmark = pytest.mark.asyncio
import asyncio
import uuid
from httpx import AsyncClient


class TestConcurrentMeteringAtBoundary:
    """A1: Race condition probe - concurrent requests when 1 slot remains."""

    async def test_concurrent_requests_only_one_succeeds_at_boundary(
        self, client: AsyncClient, auth_headers: dict, test_tenant, async_session
    ):
        """When 1 quota slot remains, 20 concurrent requests → exactly 1 event recorded."""
        from src.models.usage_event import UsageEvent, UsageType

        # Pre-fill to leave exactly 1 slot remaining (FREE plan = 5,000 API calls)
        from datetime import datetime, timezone
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
                for _ in range(4999)
            ]
            async_session.add_all(events)

        # Launch 20 concurrent requests, all wanting 1 API call
        key_base = str(uuid.uuid4())
        tasks = [
            client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": f"{key_base}-{i}"},
            )
            for i in range(20)
        ]
        responses = await asyncio.gather(*tasks)

        # Count successes (200) vs quota exceeded (429)
        success_count = sum(1 for r in responses if r.status_code == 200)
        quota_exceeded_count = sum(1 for r in responses if r.status_code == 429)

        # Exactly 1 should succeed (the first one to acquire the slot)
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert quota_exceeded_count == 19, f"Expected 19 quota exceeded, got {quota_exceeded_count}"

    async def test_concurrent_same_idempotency_key(
        self, client: AsyncClient, auth_headers: dict
    ):
        """50 concurrent requests with the same idempotency key → exactly 1 event created."""
        key = str(uuid.uuid4())

        tasks = [
            client.post(
                "/api/v1/meter",
                json={"usage_type": "api_call", "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )
            for _ in range(50)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed (idempotency guarantees same event)
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count == 50, f"Expected all 50 to succeed with idempotency, got {success_count}"

        # Verify exactly 1 event in DB
        resp = await client.get("/api/v1/usage", headers=auth_headers)
        data = resp.json()
        assert data["api_calls"]["used"] == 1
