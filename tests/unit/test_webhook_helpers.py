import pytest
import stripe


class TestExtractEventPayload:
    """Unit tests for _extract_event_payload helper."""

    def test_extract_from_dict(self):
        """Test extraction from a plain dict."""
        from src.api.v1.webhook import _extract_event_payload

        result = _extract_event_payload({"id": "evt_123", "type": "checkout.session.completed"})
        assert result == {"id": "evt_123", "type": "checkout.session.completed"}

    def test_extract_from_object_with_to_dict(self):
        """Test extraction from an object with to_dict method."""
        from src.api.v1.webhook import _extract_event_payload

        class StripeObj:
            def to_dict(self):
                return {"id": "evt_456", "type": "customer.subscription.created"}

        result = _extract_event_payload(StripeObj())
        assert result == {"id": "evt_456", "type": "customer.subscription.created"}

    def test_extract_from_object_with_dict(self):
        """Test extraction from an object with __dict__ but no to_dict."""
        from src.api.v1.webhook import _extract_event_payload

        class StripeObj:
            def __init__(self):
                self.id = "evt_789"
                self.type = "invoice.payment_succeeded"
                self._private = "skip_me"

        result = _extract_event_payload(StripeObj())
        assert result == {"id": "evt_789", "type": "invoice.payment_succeeded"}
        assert "_private" not in result

    def test_extract_from_primitive(self):
        """Test extraction from a primitive (fallback to string)."""
        from src.api.v1.webhook import _extract_event_payload

        result = _extract_event_payload("not an object")
        assert result == {"raw": "not an object"}


class TestVerifySignatureOrRaise:
    """Unit tests for _verify_signature_or_raise helper."""

    def test_verify_signature_valid(self):
        """Test that valid signature returns event without raising."""
        from src.api.v1.webhook import _verify_signature_or_raise
        from unittest.mock import MagicMock

        mock_service = MagicMock()
        mock_event = MagicMock()
        mock_event.id = "evt_valid"
        mock_service.verify_webhook_signature.return_value = mock_event

        result = _verify_signature_or_raise(
            mock_service, b"payload", "t=1,v1=abc", "whsec_secret"
        )

        assert result == mock_event
        mock_service.verify_webhook_signature.assert_called_once_with(
            b"payload", "t=1,v1=abc", "whsec_secret"
        )

    def test_verify_signature_invalid_raises_400(self):
        """Test that invalid signature raises HTTPException with 400."""
        from src.api.v1.webhook import _verify_signature_or_raise
        from fastapi import HTTPException
        from unittest.mock import MagicMock

        mock_service = MagicMock()
        mock_service.verify_webhook_signature.side_effect = (
            stripe.error.SignatureVerificationError(
                message="Invalid signature",
                sig_header="invalid",
                http_body="",
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            _verify_signature_or_raise(mock_service, b"payload", "bad_sig", "whsec")

        assert exc_info.value.status_code == 400
        assert "Invalid signature" in exc_info.value.detail
