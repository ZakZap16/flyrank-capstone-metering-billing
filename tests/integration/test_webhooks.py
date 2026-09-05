import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.plan import PlanTier
from datetime import datetime, timezone, timedelta


class StripeObjectMock:
    """Mock that supports both attribute access and JSON serialization."""
    def __init__(self, data):
        self._data = data
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    setattr(self, k, self._wrap(v))
                else:
                    setattr(self, k, v)
        elif isinstance(data, list):
            self._list = [self._wrap(item) for item in data]
    
    def _wrap(self, v):
        if isinstance(v, dict):
            return StripeObjectMock(v)
        elif isinstance(v, list):
            return [self._wrap(item) for item in v]
        return v
    
    def __getitem__(self, key):
        return self._wrap(self._data[key]) if isinstance(self._data, dict) else self._data[key]
    
    def __iter__(self):
        if isinstance(self._data, dict):
            return iter(self._data.keys())
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key, default=None):
        if isinstance(self._data, dict):
            return self._data.get(key, default)
        return default
    
    def to_dict(self):
        if isinstance(self._data, dict):
            return {k: (v.to_dict() if isinstance(v, StripeObjectMock) else v) 
                   for k, v in self._data.items()}
        return self._data


def make_stripe_session_obj():
    """Create a session object that supports both attribute and dict access."""
    return StripeObjectMock({
        "id": "cs_test_123",
        "customer": "cus_test_123",
        "subscription": "sub_test_123",
        "metadata": {"tenant_id": ""},
        "customer_details": {"email": "test@example.com"},
        "display_items": [
            {"plan": {"price": {"id": "price_pro"}}}
        ],
    })


def make_stripe_subscription_obj(stripe_sub_id="sub_test_123", status="active", 
                                 tenant_id="", cancel_at_period_end=False, canceled_at=None,
                                 price_id="pro"):
    """Create a mock Stripe subscription object."""
    return StripeObjectMock({
        "id": stripe_sub_id,
        "status": status,
        "customer": "cus_test_123",
        "metadata": {"tenant_id": tenant_id},
        "items": {
            "data": [
                {"price": {"id": price_id}}
            ]
        },
        "current_period_start": 1704067200,
        "current_period_end": 1706745600,
        "cancel_at_period_end": cancel_at_period_end,
        "canceled_at": canceled_at,
    })


def make_stripe_invoice_obj(subscription_id="sub_test_123", amount_due=4900):
    """Create a mock Stripe invoice object."""
    return StripeObjectMock({
        "id": "in_test_123",
        "subscription": subscription_id,
        "amount_due": amount_due,
    })


def make_event(event_id: str, event_type: str, data_object):
    """Create a mock Stripe event with proper data attribute."""
    from unittest.mock import PropertyMock
    event = MagicMock()
    event.id = event_id
    event.type = event_type
    # Use PropertyMock so .data returns our controlled mock
    type(event).data = PropertyMock(return_value=MagicMock(object=data_object))
    return event


@pytest.fixture
def mock_stripe_event():
    """Create a mock Stripe event object."""
    from unittest.mock import PropertyMock
    event = MagicMock()
    event.id = "evt_test_123"
    event.type = "checkout.session.completed"
    # Use PropertyMock for data to properly set .object
    type(event).data = PropertyMock(return_value=MagicMock(object=make_stripe_session_obj()))
    return event


@pytest_asyncio.fixture
async def test_subscription(async_session, test_tenant):
    """Get the existing subscription for test_tenant and set stripe_subscription_id."""
    from src.repositories.subscription_repo import SubscriptionRepository
    sub_repo = SubscriptionRepository(async_session)
    # test_tenant fixture already creates a FREE plan subscription
    # Update it to have a stripe_subscription_id for webhook tests
    sub = await sub_repo.get_active_by_tenant(test_tenant.id)
    if sub:
        sub.plan_id = PlanTier.PRO
        sub.stripe_subscription_id = "sub_test_123"
        sub.status = SubscriptionStatus.PAST_DUE
        await async_session.commit()
        await async_session.refresh(sub)
    return sub


# === Checkout Session Completed ===

@pytest.mark.asyncio
async def test_webhook_processes_checkout_completed(async_client, async_session, mock_stripe_event):
    """Test that checkout.session.completed creates tenant and subscription."""
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=mock_stripe_event), \
         patch("src.services.stripe_service.StripeService.get_customer", new_callable=AsyncMock) as mock_get_customer:
        
        mock_customer = MagicMock()
        mock_customer.email = "test@example.com"
        mock_customer.id = "cus_test_123"
        mock_get_customer.return_value = mock_customer
        
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_test_123", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_webhook_idempotency(async_client, async_session, mock_stripe_event):
    """Test that same event ID is not processed twice."""
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=mock_stripe_event), \
         patch("src.services.stripe_service.StripeService.get_customer", new_callable=AsyncMock) as mock_get_customer:
        
        mock_customer = MagicMock()
        mock_customer.email = "test@example.com"
        mock_customer.id = "cus_test_123"
        mock_get_customer.return_value = mock_customer
        
        # First request
        response1 = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_test_dup_123", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        # Second request with same event ID
        response2 = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_test_dup_123", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response1.status_code == 200
    assert response1.json()["status"] == "success"
    assert response2.json()["status"] == "already_processed"


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(async_client):
    """Test that invalid signature returns 400."""
    import stripe
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature") as mock_verify:
        mock_verify.side_effect = stripe.error.SignatureVerificationError(
            message="Invalid signature",
            sig_header="invalid_signature",
            http_body=""
        )
        
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_test_invalid", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "invalid_signature"}
        )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(async_client):
    """Test that missing signature returns 400."""
    response = await async_client.post(
        "/api/v1/webhooks/stripe",
        json={"id": "evt_test_no_sig", "type": "checkout.session.completed"}
    )
    
    assert response.status_code == 400


# === Invoice Payment Succeeded ===

@pytest.mark.asyncio
async def test_webhook_payment_succeeded(async_client, async_session, test_subscription):
    """Test that invoice.payment_succeeded reactivates a past_due subscription."""
    event = make_event(
        "evt_payment_succeeded_123",
        "invoice.payment_succeeded",
        make_stripe_invoice_obj(subscription_id="sub_test_123")
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_payment_succeeded_123", "type": "invoice.payment_succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify subscription was reactivated
    await async_session.refresh(test_subscription)
    assert test_subscription.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_webhook_payment_succeeded_no_subscription(async_client, async_session):
    """Test invoice.payment_succeeded when subscription not found in DB."""
    event = make_event(
        "evt_pay_succ_nosub_123",
        "invoice.payment_succeeded",
        make_stripe_invoice_obj(subscription_id="sub_nonexistent")
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_pay_succ_nosub_123", "type": "invoice.payment_succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    # Should still succeed (handler gracefully handles missing subscription)
    assert response.status_code == 200


# === Invoice Payment Failed ===

@pytest.mark.asyncio
async def test_webhook_payment_failed(async_client, async_session, test_subscription):
    """Test that invoice.payment_failed marks subscription as past_due."""
    # Reset to active first
    test_subscription.status = SubscriptionStatus.ACTIVE
    await async_session.commit()
    
    event = make_event(
        "evt_payment_failed_123",
        "invoice.payment_failed",
        make_stripe_invoice_obj(subscription_id="sub_test_123")
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_payment_failed_123", "type": "invoice.payment_failed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify subscription was marked past_due
    await async_session.refresh(test_subscription)
    assert test_subscription.status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_webhook_payment_failed_no_subscription(async_client, async_session):
    """Test invoice.payment_failed when subscription not found in DB."""
    event = make_event(
        "evt_pay_fail_nosub_123",
        "invoice.payment_failed",
        make_stripe_invoice_obj(subscription_id="sub_nonexistent")
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_pay_fail_nosub_123", "type": "invoice.payment_failed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200


# === Subscription Created ===

@pytest.mark.asyncio
async def test_webhook_subscription_created(async_client, async_session):
    """Test customer.subscription.created creates subscription record."""
    from src.services.auth_service import AuthService
    from src.repositories.tenant_repo import TenantRepository
    
    tenant_repo = TenantRepository(async_session)
    plain_key, key_hash = AuthService.generate_api_key()
    # Create a tenant WITHOUT subscription
    new_tenant = await tenant_repo.create(
        name="New Stripe Customer",
        email="new_customer@example.com",
        api_key_hash=key_hash,
    )
    await async_session.commit()
    
    event = make_event(
        "evt_sub_created_123",
        "customer.subscription.created",
        make_stripe_subscription_obj(
            stripe_sub_id="sub_new_123",
            status="active",
            tenant_id=str(new_tenant.id),
        )
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_sub_created_123", "type": "customer.subscription.created"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_webhook_subscription_created_existing(async_client, async_session, test_subscription):
    """Test subscription.created updates existing subscription."""
    event = make_event(
        "evt_sub_created_existing_123",
        "customer.subscription.created",
        make_stripe_subscription_obj(
            stripe_sub_id="sub_test_123",
            status="active",
        )
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_sub_created_existing_123", "type": "customer.subscription.created"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    await async_session.refresh(test_subscription)
    assert test_subscription.status == SubscriptionStatus.ACTIVE


# === Subscription Updated ===

@pytest.mark.asyncio
async def test_webhook_subscription_updated(async_client, async_session, test_subscription):
    """Test customer.subscription.updated updates subscription fields."""
    event = make_event(
        "evt_sub_updated_123",
        "customer.subscription.updated",
        make_stripe_subscription_obj(
            stripe_sub_id="sub_test_123",
            status="active",
            cancel_at_period_end=True,
        )
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_sub_updated_123", "type": "customer.subscription.updated"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    await async_session.refresh(test_subscription)
    assert test_subscription.cancel_at_period_end == True


# === Subscription Deleted ===

@pytest.mark.asyncio
async def test_webhook_subscription_deleted(async_client, async_session, test_subscription):
    """Test customer.subscription.deleted marks subscription as canceled."""
    event = make_event(
        "evt_sub_deleted_123",
        "customer.subscription.deleted",
        make_stripe_subscription_obj(
            stripe_sub_id="sub_test_123",
            status="canceled",
        )
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_sub_deleted_123", "type": "customer.subscription.deleted"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    await async_session.refresh(test_subscription)
    assert test_subscription.status == SubscriptionStatus.CANCELED


# === Trial Will End ===

@pytest.mark.asyncio
async def test_webhook_subscription_trial_will_end(async_client, async_session, test_subscription):
    """Test customer.subscription.trial_will_end logs warning."""
    event = make_event(
        "evt_trial_end_123",
        "customer.subscription.trial_will_end",
        make_stripe_subscription_obj(
            stripe_sub_id="sub_test_123",
            status="trialing",
            tenant_id=str(test_subscription.tenant_id),
        )
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_trial_end_123", "type": "customer.subscription.trial_will_end"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"


# === Invoice Upcoming ===

@pytest.mark.asyncio
async def test_webhook_invoice_upcoming(async_client, async_session, test_subscription):
    """Test invoice.upcoming handler logs notification."""
    event = make_event(
        "evt_invoice_upcoming_123",
        "invoice.upcoming",
        make_stripe_invoice_obj(subscription_id="sub_test_123", amount_due=4900)
    )
    
    with patch("src.services.stripe_service.StripeService.verify_webhook_signature", return_value=event):
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"id": "evt_invoice_upcoming_123", "type": "invoice.upcoming"},
            headers={"Stripe-Signature": "valid_signature"}
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
