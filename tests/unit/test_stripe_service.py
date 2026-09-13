import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import stripe


class TestStripeService:
    """Unit tests for StripeService."""
    
    def test_init_uses_settings_api_key(self):
        """Test that StripeService uses STRIPE_API_KEY from settings."""
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_custom"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            
            assert service.client.api_key == "sk_test_custom"
    
    def test_init_accepts_explicit_api_key(self):
        """Test that explicit api_key overrides settings."""
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_settings"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService(api_key="sk_test_explicit")
            
            assert service.client.api_key == "sk_test_explicit"
    
    @pytest.mark.asyncio
    async def test_create_customer_calls_stripe_sdk(self):
        """Test create_customer calls stripe.Customer.create with correct args."""
        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        
        mock_customer_class = MagicMock()
        mock_customer_class.create = AsyncMock(return_value=mock_customer)
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.Customer = mock_customer_class
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            result = await service.create_customer(
                email="test@example.com",
                metadata={"tenant_id": "test-123"}
            )
            
            mock_customer_class.create.assert_called_once_with(
                email="test@example.com",
                metadata={"tenant_id": "test-123"}
            )
            assert result.id == "cus_123"
    
    @pytest.mark.asyncio
    async def test_create_checkout_session_calls_stripe_sdk(self):
        """Test create_checkout_session calls Stripe with correct params."""
        mock_session = MagicMock()
        mock_session.id = "cs_123"
        mock_session.url = "https://checkout.stripe.com/cs"
        
        mock_checkout_session = MagicMock()
        mock_checkout_session.create = AsyncMock(return_value=mock_session)
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.checkout.Session = mock_checkout_session
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            result = await service.create_checkout_session(
                customer_id="cus_123",
                price_id="price_pro",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={"tenant_id": "test-123"}
            )
            
            mock_checkout_session.create.assert_called_once()
            call_kwargs = mock_checkout_session.create.call_args.kwargs
            assert call_kwargs["customer"] == "cus_123"
            assert call_kwargs["mode"] == "subscription"
            assert call_kwargs["line_items"] == [{"price": "price_pro", "quantity": 1}]
            assert result.url == "https://checkout.stripe.com/cs"
    
    @pytest.mark.asyncio
    async def test_create_portal_session_calls_stripe_sdk(self):
        """Test create_portal_session calls Stripe billing portal with correct params."""
        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/portal"
        
        mock_portal_session = MagicMock()
        mock_portal_session.create = AsyncMock(return_value=mock_portal)
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.billing_portal.Session = mock_portal_session
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            result = await service.create_portal_session(
                customer_id="cus_123",
                return_url="https://example.com/billing"
            )
            
            mock_portal_session.create.assert_called_once_with(
                customer="cus_123",
                return_url="https://example.com/billing"
            )
            assert result.url == "https://billing.stripe.com/portal"
    
    def test_verify_webhook_signature_valid(self):
        """Test verify_webhook_signature calls Stripe Webhook.construct_event."""
        mock_event = MagicMock()
        mock_event.id = "evt_test"
        
        mock_webhook = MagicMock()
        mock_webhook.construct_event.return_value = mock_event
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.Webhook = mock_webhook
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            result = service.verify_webhook_signature(
                b'{"test": "payload"}',
                "t=123,v1=abc",
                "whsec_test"
            )
            
            mock_webhook.construct_event.assert_called_once_with(
                b'{"test": "payload"}',
                "t=123,v1=abc",
                "whsec_test"
            )
            assert result.id == "evt_test"
    
    def test_verify_webhook_signature_invalid_raises(self):
        """Test verify_webhook_signature raises SignatureVerificationError on invalid sig."""
        mock_webhook = MagicMock()
        mock_webhook.construct_event.side_effect = stripe.error.SignatureVerificationError(
            message="Invalid signature",
            sig_header="invalid",
            http_body=""
        )
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.Webhook = mock_webhook
        mock_stripe.error.SignatureVerificationError = stripe.error.SignatureVerificationError
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            with pytest.raises(stripe.error.SignatureVerificationError):
                service.verify_webhook_signature(b'{}', "invalid", "whsec_test")
    
    @pytest.mark.asyncio
    async def test_get_customer_calls_stripe_sdk(self):
        """Test get_customer calls stripe.Customer.retrieve with correct id."""
        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        mock_customer.email = "test@example.com"
        
        mock_customer_class = MagicMock()
        mock_customer_class.retrieve = AsyncMock(return_value=mock_customer)
        
        mock_stripe = MagicMock()
        mock_stripe.api_key = "sk_test_xxx"
        mock_stripe.Customer = mock_customer_class
        
        with patch("src.services.stripe_service.get_settings") as mock_settings:
            mock_settings.return_value.STRIPE_API_KEY = "sk_test_xxx"
            mock_settings.return_value.stripe_api_key = None
            
            from src.services.stripe_service import StripeService
            service = StripeService()
            service.client = mock_stripe
            
            result = await service.get_customer("cus_123")
            
            mock_customer_class.retrieve.assert_called_once_with("cus_123")
            assert result.email == "test@example.com"
    
