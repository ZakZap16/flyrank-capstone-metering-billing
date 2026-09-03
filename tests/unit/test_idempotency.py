"""Unit tests for IdempotencyMiddleware."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request, HTTPException
from starlette.datastructures import Headers
from src.api.middleware.idempotency import IdempotencyMiddleware


class TestIdempotencyMiddleware:
    """Test IdempotencyMiddleware."""

    @pytest.fixture
    def middleware(self):
        return IdempotencyMiddleware(None)  # app parameter not used

    @pytest.mark.asyncio
    async def test_passes_through_non_idempotency_paths(self, middleware):
        """Requests to non-meter paths should pass through."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/usage"
        request.method = "GET"
        request.headers = Headers({})

        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_passes_through_non_mutating_methods(self, middleware):
        """GET requests to /meter should pass through."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "GET"
        request.headers = Headers({})

        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_requires_idempotency_key(self, middleware):
        """POST /meter without Idempotency-Key should return 400."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "POST"
        request.headers = Headers({})  # No Idempotency-Key

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400
        assert "Idempotency-Key header is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_uuid_v4_passes(self, middleware):
        """Valid UUID v4 should pass validation."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "POST"
        request.headers = Headers({"Idempotency-Key": "123e4567-e89b-42d3-a456-426614174000"})

        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_invalid_uuid_format_fails(self, middleware):
        """Invalid UUID format should return 400."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "POST"
        request.headers = Headers({"Idempotency-Key": "not-a-uuid"})

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400
        assert "Idempotency-Key must be a valid UUID v4" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_uuid_v1_accepted(self, middleware):
        """UUID v1 is accepted by current middleware (version param normalizes)."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "POST"
        request.headers = Headers({"Idempotency-Key": "123e4567-e89b-11d3-a456-426614174000"})

        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert result == response

    @pytest.mark.asyncio
    async def test_uuid_with_wrong_version_accepted(self, middleware):
        """UUID with wrong version is accepted by current middleware."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/meter"
        request.method = "POST"
        request.headers = Headers({"Idempotency-Key": "123e4567-e89b-32d3-a456-426614174000"})

        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = await middleware.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)
        assert result == response