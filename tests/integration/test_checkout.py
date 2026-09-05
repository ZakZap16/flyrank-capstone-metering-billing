import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.models.usage_event import UsageType


@pytest.mark.asyncio
async def test_checkout_session_creates_stripe_session(async_client, test_tenant):
    """Test that checkout endpoint creates a Stripe checkout session."""
    # First update the test tenant to have a stripe customer ID so we skip the create_customer call
    with patch("src.services.stripe_service.StripeService.create_checkout_session", new_callable=AsyncMock) as mock_checkout:
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_checkout.return_value = mock_session
        
        response = await async_client.post(
            "/api/v1/checkout/session",
            json={"plan_tier": "pro"},
            headers={"X-Tenant-ID": str(test_tenant.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "checkout_session_id" in data
    assert "url" in data


@pytest.mark.asyncio
async def test_checkout_invalid_plan_tier(async_client, test_tenant):
    """Test that invalid plan_tier returns 422 validation error."""
    response = await async_client.post(
        "/api/v1/checkout/session",
        json={"plan_tier": "invalid"},
        headers={"X-Tenant-ID": str(test_tenant.id)}
    )
    
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_checkout_no_stripe_customer(async_client, test_tenant):
    """Test checkout when tenant has no Stripe customer (creates one)."""
    # Mock StripeService to return a customer
    with patch("src.services.stripe_service.StripeService.create_customer", new_callable=AsyncMock) as mock_create_customer, \
         patch("src.services.stripe_service.StripeService.create_checkout_session", new_callable=AsyncMock) as mock_checkout:
        
        mock_customer = MagicMock()
        mock_customer.id = "cus_test_123"
        mock_create_customer.return_value = mock_customer
        
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_checkout.return_value = mock_session
        
        response = await async_client.post(
            "/api/v1/checkout/session",
            json={"plan_tier": "pro"},
            headers={"X-Tenant-ID": str(test_tenant.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "checkout_session_id" in data
    assert data["url"] == "https://checkout.stripe.com/test"


@pytest.mark.asyncio
async def test_checkout_missing_plan_tier(async_client, test_tenant):
    """Test that missing plan_tier returns 422 validation error."""
    response = await async_client.post(
        "/api/v1/checkout/session",
        json={},
        headers={"X-Tenant-ID": str(test_tenant.id)}
    )
    
    assert response.status_code == 422