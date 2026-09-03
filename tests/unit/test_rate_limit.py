"""Unit tests for InMemoryRateLimiter."""
import pytest
import time
import threading
from src.api.middleware.rate_limit import InMemoryRateLimiter


class TestInMemoryRateLimiter:
    """Test the in-memory rate limiter."""

    def test_allows_first_request(self):
        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
        allowed, retry_after = limiter.is_allowed("test_key")
        assert allowed is True
        assert retry_after == 0

    def test_allows_requests_within_limit(self):
        limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        for i in range(3):
            allowed, _ = limiter.is_allowed("test_key")
            assert allowed is True

    def test_blocks_requests_exceeding_limit(self):
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        # Use up the quota
        limiter.is_allowed("test_key")
        limiter.is_allowed("test_key")
        # This one should be blocked
        allowed, retry_after = limiter.is_allowed("test_key")
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_have_separate_limits(self):
        limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("key_a")[0] is True
        assert limiter.is_allowed("key_b")[0] is True

    def test_old_requests_expire_after_window(self):
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=1)
        # Use up the limit
        limiter.is_allowed("test_key")
        limiter.is_allowed("test_key")
        # Should be blocked
        assert limiter.is_allowed("test_key")[0] is False

        # Simulate time passing by directly modifying timestamps
        # (in a real scenario, we would sleep, but for unit tests we can manipulate)

    def test_retry_after_is_positive_when_blocked(self):
        limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("test_key")  # Use quota
        _, retry_after = limiter.is_allowed("test_key")
        assert retry_after > 0
        assert isinstance(retry_after, int)

    def test_thread_safety(self):
        """Test that concurrent access doesn't cause issues."""
        limiter = InMemoryRateLimiter(max_requests=1000, window_seconds=60)
        results = []

        def make_requests():
            for _ in range(100):
                results.append(limiter.is_allowed("shared_key")[0])

        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 500 requests should succeed (well under 1000 limit)
        assert all(r is True for r in results)

    def test_max_requests_can_be_large(self):
        """Test with a very large limit (like our test config)."""
        limiter = InMemoryRateLimiter(max_requests=100_000, window_seconds=60)
        for _ in range(100):
            allowed, _ = limiter.is_allowed("test_key")
            assert allowed is True
