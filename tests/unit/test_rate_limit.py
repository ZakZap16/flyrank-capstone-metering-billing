"""Unit tests for RedisRateLimiter."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.middleware.rate_limit import RedisRateLimiter


def _make_mock_redis(pipeline_result, zrange_result=None):
    """Create a mock Redis with async pipeline.execute()."""
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=pipeline_result)
    mock_pipe.zremrangebyscore = MagicMock(return_value=MagicMock())
    mock_pipe.zcard = MagicMock(return_value=MagicMock())
    mock_pipe.zadd = MagicMock(return_value=MagicMock())
    mock_pipe.expire = MagicMock(return_value=MagicMock())

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    if zrange_result is not None:
        mock_redis.zrange = AsyncMock(return_value=zrange_result)
    return mock_redis


class TestRedisRateLimiter:
    """Test the Redis-backed rate limiter."""

    @pytest.mark.asyncio
    async def test_allows_first_request(self):
        """First request should always be allowed."""
        mock_redis = _make_mock_redis([0, 0, 1, True])

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=5, window_seconds=60)
            allowed, retry_after = await limiter.is_allowed("test_key")

        assert allowed is True
        assert retry_after == 0

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self):
        """Requests within limit should be allowed."""
        mock_redis = _make_mock_redis([0, 1, 1, True])

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=3, window_seconds=60)
            for i in range(3):
                allowed, _ = await limiter.is_allowed("test_key")
                assert allowed is True

    @pytest.mark.asyncio
    async def test_blocks_requests_exceeding_limit(self):
        """Requests exceeding limit should be blocked."""
        mock_redis = _make_mock_redis(
            pipeline_result=[0, 2, 1, True],
            zrange_result=[(b"1000000.0", 1000000.0)],
        )

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=2, window_seconds=60)
            allowed, retry_after = await limiter.is_allowed("test_key")

        assert allowed is False
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_different_keys_have_separate_limits(self):
        """Different keys should have separate rate limits."""
        mock_redis = _make_mock_redis([0, 0, 1, True])

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=1, window_seconds=60)
            allowed_a, _ = await limiter.is_allowed("key_a")
            allowed_b, _ = await limiter.is_allowed("key_b")

        assert allowed_a is True
        assert allowed_b is True

    @pytest.mark.asyncio
    async def test_retry_after_is_positive_when_blocked(self):
        """Retry-after should be positive when blocked."""
        mock_redis = _make_mock_redis(
            pipeline_result=[0, 1, 1, True],
            zrange_result=[(b"1000000.0", 1000000.0)],
        )

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=1, window_seconds=60)
            _, retry_after = await limiter.is_allowed("test_key")

        assert retry_after > 0
        assert isinstance(retry_after, int)

    @pytest.mark.asyncio
    async def test_falls_back_to_allow_when_redis_unavailable(self):
        """Should allow requests when Redis is unavailable (fail open)."""
        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, side_effect=Exception("Redis down")):
            limiter = RedisRateLimiter(max_requests=1, window_seconds=60)
            allowed, retry_after = await limiter.is_allowed("test_key")

        assert allowed is True
        assert retry_after == 0

    @pytest.mark.asyncio
    async def test_max_requests_can_be_large(self):
        """Test with a very large limit (like our test config)."""
        mock_redis = _make_mock_redis([0, 50, 1, True])

        with patch("src.api.middleware.rate_limit.get_redis", new_callable=AsyncMock, return_value=mock_redis):
            limiter = RedisRateLimiter(max_requests=100_000, window_seconds=60)
            for _ in range(100):
                allowed, _ = await limiter.is_allowed("test_key")
                assert allowed is True
