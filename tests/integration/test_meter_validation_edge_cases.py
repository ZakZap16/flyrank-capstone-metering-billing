import pytest
pytestmark = pytest.mark.asyncio
from httpx import AsyncClient


class TestMeterRequestValidation:
    """Test MeterRequest schema validation for invalid inputs."""

    async def test_zero_qty_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 0},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174000"},
        )
        assert resp.status_code == 422

    async def test_negative_qty_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": -1},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174001"},
        )
        assert resp.status_code == 422

    async def test_qty_exceeds_max_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 10_000_001},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174002"},
        )
        assert resp.status_code == 422

    async def test_missing_qty_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call"},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174003"},
        )
        assert resp.status_code == 422

    async def test_missing_usage_type_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"qty": 1},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174004"},
        )
        assert resp.status_code == 422

    async def test_invalid_usage_type_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "not_a_real_type", "qty": 1},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174005"},
        )
        assert resp.status_code == 422

    async def test_extra_field_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/meter",
            json={"usage_type": "api_call", "qty": 1, "extra_field": "should_fail"},
            headers={**auth_headers, "Idempotency-Key": "123e4567-e89b-42d3-a456-426614174006"},
        )
        assert resp.status_code == 422
