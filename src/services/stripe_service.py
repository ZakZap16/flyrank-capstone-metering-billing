import stripe
from src.config.settings import get_settings
from uuid import UUID


class StripeService:
    def __init__(self, api_key: str = None):
        settings = get_settings()
        self.client = stripe
        api_key = api_key or getattr(settings, 'STRIPE_API_KEY', None) or getattr(settings, 'stripe_api_key', None)
        self.client.api_key = api_key
    
    async def create_customer(self, email: str, metadata: dict) -> stripe.Customer:
        return await self.client.Customer.create(
            email=email,
            metadata=metadata
        )
    
    async def create_checkout_session(
        self, 
        customer_id: str, 
        price_id: str, 
        success_url: str, 
        cancel_url: str,
        metadata: dict
    ) -> stripe.checkout.Session:
        return await self.client.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )
    
    async def create_portal_session(self, customer_id: str, return_url: str) -> stripe.billing_portal.Session:
        return await self.client.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
    
    def verify_webhook_signature(self, payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
        return self.client.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    
    async def get_customer(self, customer_id: str) -> stripe.Customer:
        return await self.client.Customer.retrieve(customer_id)
