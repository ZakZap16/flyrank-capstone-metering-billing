"""Unit tests for auth middleware get_current_tenant."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from src.api.middleware.auth import get_current_tenant
from src.models.tenant import Tenant


class TestGetCurrentTenant:
    """Test get_current_tenant middleware function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock Tenant."""
        tenant = MagicMock(spec=Tenant)
        tenant.id = "123e4567-e89b-42d3-a456-426614174000"
        tenant.api_key_hash = "test_hash"
        return tenant

    @pytest.fixture
    def valid_headers(self):
        """Valid authentication headers."""
        return {"X-Tenant-ID": "123e4567-e89b-42d3-a456-426614174000"}

    @pytest.mark.asyncio
    async def test_valid_x_tenant_id(self, mock_tenant, valid_headers):
        """Valid X-Tenant-ID should return tenant."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Patch verify_api_key to ensure it returns False so test fails if called
        with patch("src.api.middleware.auth.AuthService.verify_api_key", return_value=True):
            result = await get_current_tenant(
                x_tenant_id=valid_headers["X-Tenant-ID"],
                db=mock_session
            )
        assert result == mock_tenant

    @pytest.mark.asyncio
    async def test_invalid_x_tenant_id_format(self):
        """Invalid X-Tenant-ID format should raise 401."""
        mock_session = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                x_tenant_id="invalid-format",
                db=mock_session
            )

        assert exc_info.value.status_code == 401
        assert "Invalid X-Tenant-ID format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_tenant_not_found(self, valid_headers):
        """Valid format but tenant not found should raise 401."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                x_tenant_id=valid_headers["X-Tenant-ID"],
                db=mock_session
            )

        assert exc_info.value.status_code == 401
        assert "Tenant not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_api_key_verification(self, mock_tenant, valid_headers):
        """Valid API key should pass verification."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.api.middleware.auth.AuthService.verify_api_key", return_value=True) as mock_verify:
            result = await get_current_tenant(
                x_tenant_id=valid_headers["X-Tenant-ID"],
                x_api_key="valid-api-key",
                db=mock_session
            )
        assert result == mock_tenant
        mock_verify.assert_called_once_with("valid-api-key", "test_hash")

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self, mock_tenant, valid_headers):
        """Invalid API key should raise 401."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.api.middleware.auth.AuthService.verify_api_key", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant(
                    x_tenant_id=valid_headers["X-Tenant-ID"],
                    x_api_key="wrong-key",
                    db=mock_session
                )

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_api_key_skips_verification(self, mock_tenant, valid_headers):
        """No API key provided should skip verification and return tenant."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Pass x_api_key=None explicitly to override Header(None) default
        with patch("src.api.middleware.auth.AuthService.verify_api_key") as mock_verify:
            result = await get_current_tenant(
                x_tenant_id=valid_headers["X-Tenant-ID"],
                x_api_key=None,
                db=mock_session
            )
        assert result == mock_tenant
        mock_verify.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_api_key_and_no_hash_skips_verification(self, valid_headers):
        """No API key and tenant without hash should skip verification."""
        tenant_no_hash = MagicMock(spec=Tenant)
        tenant_no_hash.id = valid_headers["X-Tenant-ID"]
        tenant_no_hash.api_key_hash = None

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tenant_no_hash
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.api.middleware.auth.AuthService.verify_api_key") as mock_verify:
            result = await get_current_tenant(
                x_tenant_id=valid_headers["X-Tenant-ID"],
                db=mock_session
            )
        assert result == tenant_no_hash
        mock_verify.assert_not_called()