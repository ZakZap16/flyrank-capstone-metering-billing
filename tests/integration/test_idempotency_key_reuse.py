import pytest
pytestmark = pytest.mark.asyncio
import uuid
from httpx import AsyncClient


class TestIdempotencyKeyReuseAcrossTypes:
    """A2: Same idempotency key with different usage_type = separate events.

    The unique constraint is on (tenant_id, idempotency_key, usage_type).
    So same key + different type = two separate events.
    """

    async def test_same_key_different_type_creates_two_events(
        self, client: AsyncClient, auth_headers: dict
    ):
        key = str(uuid.uuid4())

        resp1 = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp1.status_code == 200
        event1 = resp1.json()

        resp2 = await client.post(
            "/api/v1/meter",
            json={"usage_type": "input_tokens", "qty": 100},
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert resp2.status_code == 200
        event2 = resp2.json()

        assert event1["usage_event_id"] != event2["usage_event_id"]
        assert event1["usage_type"] != event2["usage_type"]

    async def test_same_key_all_five_types(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Same key used with all 5 usage types creates 5 distinct events."""
        key = str(uuid.uuid4())
        event_ids = set()
        types_submitted = set()

        for usage_type in [
            "api_call",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_tokens",
        ]:
            resp = await client.post(
                "/api/v1/meter",
                json={"usage_type": usage_type, "qty": 1},
                headers={**auth_headers, "Idempotency-Key": key},
            )
            assert resp.status_code == 200
            data = resp.json()
            event_ids.add(data["usage_event_id"])
            types_submitted.add(data["usage_type"])

        # 5 events, 5 distinct IDs, 5 distinct types
        assert len(event_ids) == 5
        assert len(types_submitted) == 5
