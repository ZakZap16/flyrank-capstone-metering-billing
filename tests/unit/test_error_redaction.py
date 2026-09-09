"""Tests for secret redaction in the error handler."""
from src.api.middleware.error_handling import _redact


class TestRedact:
    def test_redacts_stripe_test_key(self):
        raw = "Authentication failed: sk_test_abc123xyz"
        assert "sk_test_REDACTED" in _redact(raw)
        assert "sk_test_abc123xyz" not in _redact(raw)

    def test_redacts_stripe_live_key(self):
        raw = "Error with sk_live_real123key"
        assert "sk_live_REDACTED" in _redact(raw)
        assert "sk_live_real123key" not in _redact(raw)

    def test_redacts_webhook_secret(self):
        raw = "whsec_abc123 signature mismatch"
        assert "whsec_REDACTED" in _redact(raw)
        assert "whsec_abc123" not in _redact(raw)

    def test_redacts_database_url(self):
        raw = "postgresql://app_user:secret_password@localhost:5432/db"
        assert "REDACTED" in _redact(raw)
        assert "secret_password" not in _redact(raw)

    def test_redacts_password_param(self):
        raw = "connection failed: password=mysecret123&host=db"
        assert "password=REDACTED" in _redact(raw)
        assert "mysecret123" not in _redact(raw)

    def test_no_secrets_unchanged(self):
        raw = "No secrets here, just a normal error message"
        assert _redact(raw) == raw

    def test_multiple_secrets_redacted(self):
        raw = "key=sk_test_abc secret=whsec_xyz password=foo123"
        redacted = _redact(raw)
        assert "sk_test_REDACTED" in redacted
        assert "whsec_REDACTED" in redacted
        assert "password=REDACTED" in redacted
        assert "foo123" not in redacted
