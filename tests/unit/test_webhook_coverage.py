import pytest
pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.v1.webhook import (
    _extract_event_payload,
    _verify_signature_or_raise,
    _process_stripe_event,
)


class TestExtractEventPayload:
    def test_dict_passthrough(self):
        d = {"key": "value"}
        assert _extract_event_payload(d) == d

    def test_object_with_to_dict(self):
        obj = MagicMock()
        obj.to_dict.return_value = {"a": 1}
        result = _extract_event_payload(obj)
        assert result == {"a": 1}

    def test_object_with_dunder_dict(self):
        obj = MagicMock(spec=["foo", "bar"])
        obj.foo = "hello"
        obj.bar = 42
        result = _extract_event_payload(obj)
        assert "foo" in result or "bar" in result

    def test_plain_object_fallback(self):
        obj = "raw string"
        result = _extract_event_payload(obj)
        assert result == {"raw": "raw string"}


class TestVerifySignatureOrRaise:
    def test_valid_signature_returns_event(self):
        mock_service = MagicMock()
        mock_event = MagicMock()
        mock_service.verify_webhook_signature.return_value = mock_event
        result = _verify_signature_or_raise(mock_service, b"payload", "sig", "secret")
        assert result is mock_event

    def test_invalid_signature_raises_400(self):
        import stripe
        from fastapi import HTTPException
        mock_service = MagicMock()
        mock_service.verify_webhook_signature.side_effect = stripe.error.SignatureVerificationError(
            message="bad sig", sig_header="bad", http_body=""
        )
        with pytest.raises(HTTPException) as exc_info:
            _verify_signature_or_raise(mock_service, b"payload", "sig", "secret")
        assert exc_info.value.status_code == 400


class TestProcessEventDispatch:
    async def test_unhandled_event_type_logged(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "some.unknown.event"
        event.data.object = {}

        with patch("src.api.v1.webhook.logger") as mock_logger:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_logger.info.assert_called()
            assert "unhandled_stripe_event_type" in mock_logger.info.call_args[0][0]

    async def test_checkout_completed_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "checkout.session.completed"
        session_obj = MagicMock()
        session_obj.metadata = {}
        session_obj.customer = "cus_123"
        session_obj.subscription = "sub_123"
        type(event).data = PropertyMock(return_value=MagicMock(object=session_obj))

        mock_stripe = MagicMock()
        mock_quota = MagicMock()
        mock_tenant = MagicMock()
        mock_sub = MagicMock()
        mock_plan = MagicMock()
        mock_auth = MagicMock()
        mock_settings = MagicMock()

        with patch("src.api.v1.webhook._handle_checkout_completed", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, mock_stripe, mock_quota, mock_tenant,
                mock_sub, mock_plan, mock_auth, mock_settings
            )
            mock_handler.assert_awaited_once()

    async def test_payment_succeeded_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "invoice.payment_succeeded"
        invoice = MagicMock()
        invoice.subscription = "sub_123"
        type(event).data = PropertyMock(return_value=MagicMock(object=invoice))

        with patch("src.api.v1.webhook._handle_payment_succeeded", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_handler.assert_awaited_once()

    async def test_payment_failed_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "invoice.payment_failed"
        invoice = MagicMock()
        invoice.subscription = "sub_123"
        type(event).data = PropertyMock(return_value=MagicMock(object=invoice))

        with patch("src.api.v1.webhook._handle_payment_failed", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_handler.assert_awaited_once()

    async def test_subscription_deleted_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "customer.subscription.deleted"
        sub = MagicMock()
        sub.id = "sub_123"
        type(event).data = PropertyMock(return_value=MagicMock(object=sub))

        with patch("src.api.v1.webhook._handle_subscription_deleted", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_handler.assert_awaited_once()

    async def test_trial_will_end_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "customer.subscription.trial_will_end"
        sub = MagicMock()
        sub.id = "sub_123"
        sub.metadata = {"tenant_id": "t1"}
        type(event).data = PropertyMock(return_value=MagicMock(object=sub))

        with patch("src.api.v1.webhook._handle_subscription_trial_will_end", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_handler.assert_awaited_once()

    async def test_invoice_upcoming_dispatches(self):
        from unittest.mock import PropertyMock
        event = MagicMock()
        event.type = "invoice.upcoming"
        invoice = MagicMock()
        invoice.id = "in_123"
        invoice.amount_due = 5000
        type(event).data = PropertyMock(return_value=MagicMock(object=invoice))

        with patch("src.api.v1.webhook._handle_invoice_upcoming", new_callable=AsyncMock) as mock_handler:
            await _process_stripe_event(
                event, MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock()
            )
            mock_handler.assert_awaited_once()
