"""Unit tests for AuthService (API key generation and verification)."""
import pytest
from src.services.auth_service import AuthService


class TestGenerateApiKey:
    """Test API key generation."""

    def test_returns_tuple_of_two_strings(self):
        plain, hashed = AuthService.generate_api_key()
        assert isinstance(plain, str)
        assert isinstance(hashed, str)
        assert len(plain) > 0
        assert len(hashed) > 0

    def test_plain_and_hash_are_different(self):
        plain, hashed = AuthService.generate_api_key()
        assert plain != hashed

    def test_generates_unique_keys(self):
        plain1, _ = AuthService.generate_api_key()
        plain2, _ = AuthService.generate_api_key()
        assert plain1 != plain2

    def test_hash_is_bcrypt_format(self):
        _, hashed = AuthService.generate_api_key()
        # bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")

    def test_plain_key_is_urlsafe(self):
        plain, _ = AuthService.generate_api_key()
        # tokens_urlsafe uses only URL-safe characters
        # No spaces, no special chars outside the url-safe set
        for ch in plain:
            assert ch.isalnum() or ch in "-_"


class TestVerifyApiKey:
    """Test API key verification."""

    def test_valid_key_verifies_successfully(self):
        plain, hashed = AuthService.generate_api_key()
        assert AuthService.verify_api_key(plain, hashed) is True

    def test_invalid_key_returns_false(self):
        plain, hashed = AuthService.generate_api_key()
        wrong_key = plain + "x"
        assert AuthService.verify_api_key(wrong_key, hashed) is False

    def test_corrupted_hash_returns_false(self):
        plain, _ = AuthService.generate_api_key()
        # Not a valid bcrypt hash
        assert AuthService.verify_api_key(plain, "not-a-valid-bcrypt-hash") is False

    def test_empty_hash_returns_false(self):
        plain, _ = AuthService.generate_api_key()
        assert AuthService.verify_api_key(plain, "") is False

    def test_empty_key_returns_false(self):
        _, hashed = AuthService.generate_api_key()
        assert AuthService.verify_api_key("", hashed) is False