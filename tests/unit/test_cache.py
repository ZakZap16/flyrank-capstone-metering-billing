import pytest
pytestmark = pytest.mark.asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.config import cache as cache_mod


@pytest.fixture(autouse=True)
def reset_cache_globals():
    """Reset module-level globals before each test."""
    cache_mod._pool = None
    cache_mod._last_connection_attempt = 0
    yield
    cache_mod._pool = None
    cache_mod._last_connection_attempt = 0


class TestGetRedis:
    async def test_returns_existing_pool(self):
        mock_pool = AsyncMock()
        cache_mod._pool = mock_pool
        result = await cache_mod.get_redis()
        assert result is mock_pool

    async def test_returns_none_during_cooldown(self):
        cache_mod._last_connection_attempt = 999999999
        result = await cache_mod.get_redis()
        assert result is None

    @patch("src.config.cache.get_settings")
    @patch("src.config.cache.aioredis.from_url")
    async def test_creates_pool_on_success(self, mock_from_url, mock_settings):
        mock_settings.return_value = MagicMock(REDIS_URL="redis://localhost:6379/0")
        mock_pool = AsyncMock()
        mock_from_url.return_value = mock_pool
        result = await cache_mod.get_redis()
        assert result is mock_pool
        assert cache_mod._pool is mock_pool
        mock_pool.ping.assert_awaited_once()

    @patch("src.config.cache.get_settings")
    @patch("src.config.cache.aioredis.from_url")
    async def test_returns_none_on_connection_failure(self, mock_from_url, mock_settings):
        mock_settings.return_value = MagicMock(REDIS_URL="redis://localhost:6379/0")
        mock_from_url.return_value = AsyncMock(ping=AsyncMock(side_effect=ConnectionError("refused")))
        result = await cache_mod.get_redis()
        assert result is None
        assert cache_mod._pool is None


class TestCloseRedis:
    async def test_closes_existing_pool(self):
        mock_pool = AsyncMock()
        cache_mod._pool = mock_pool
        await cache_mod.close_redis()
        mock_pool.aclose.assert_awaited_once()
        assert cache_mod._pool is None

    async def test_noop_when_no_pool(self):
        cache_mod._pool = None
        await cache_mod.close_redis()


class TestCacheGet:
    @patch("src.config.cache.get_redis", new_callable=AsyncMock, return_value=None)
    async def test_returns_none_when_redis_unavailable(self, _):
        result = await cache_mod.cache_get("key")
        assert result is None

    @patch("src.config.cache.get_redis")
    async def test_returns_parsed_json(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=json.dumps({"foo": "bar"}))
        mock_get_redis.return_value = mock_r
        result = await cache_mod.cache_get("key")
        assert result == {"foo": "bar"}

    @patch("src.config.cache.get_redis")
    async def test_returns_none_on_miss(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_r
        result = await cache_mod.cache_get("key")
        assert result is None

    @patch("src.config.cache.get_redis")
    async def test_returns_none_on_json_error(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value="not-json{{{")
        mock_get_redis.return_value = mock_r
        result = await cache_mod.cache_get("key")
        assert result is None


class TestCacheSet:
    @patch("src.config.cache.get_redis", new_callable=AsyncMock, return_value=None)
    async def test_noop_when_redis_unavailable(self, _):
        await cache_mod.cache_set("key", {"a": 1})

    @patch("src.config.cache.get_redis")
    async def test_sets_value_with_ttl(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_set("key", {"a": 1}, ttl_seconds=30)
        mock_r.set.assert_awaited_once()
        args = mock_r.set.call_args
        assert args[0][0] == "key"
        assert json.loads(args[0][1]) == {"a": 1}
        assert args[1]["ex"] == 30

    @patch("src.config.cache.get_redis")
    async def test_noop_on_redis_error(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.set = AsyncMock(side_effect=Exception("connection lost"))
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_set("key", {"a": 1})


class TestCacheDelete:
    @patch("src.config.cache.get_redis", new_callable=AsyncMock, return_value=None)
    async def test_noop_when_redis_unavailable(self, _):
        await cache_mod.cache_delete("key")

    @patch("src.config.cache.get_redis")
    async def test_deletes_key(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_delete("key")
        mock_r.delete.assert_awaited_once_with("key")

    @patch("src.config.cache.get_redis")
    async def test_noop_on_redis_error(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.delete = AsyncMock(side_effect=Exception("fail"))
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_delete("key")


class TestCacheDeletePattern:
    @patch("src.config.cache.get_redis", new_callable=AsyncMock, return_value=None)
    async def test_noop_when_redis_unavailable(self, _):
        await cache_mod.cache_delete_pattern("prefix:*")

    @patch("src.config.cache.get_redis")
    async def test_deletes_matching_keys(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.scan = AsyncMock(side_effect=[
            (0, ["key1", "key2"]),
        ])
        mock_r.delete = AsyncMock()
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_delete_pattern("prefix:*")
        mock_r.delete.assert_awaited_once_with("key1", "key2")

    @patch("src.config.cache.get_redis")
    async def test_noop_on_redis_error(self, mock_get_redis):
        mock_r = AsyncMock()
        mock_r.scan = AsyncMock(side_effect=Exception("fail"))
        mock_get_redis.return_value = mock_r
        await cache_mod.cache_delete_pattern("prefix:*")


class TestIdempotencyHelpers:
    @patch("src.config.cache.cache_get", new_callable=AsyncMock, return_value=None)
    async def test_check_idempotency_key_miss(self, _):
        result = await cache_mod.check_idempotency_key("t1", "k1", "api_call")
        assert result is None

    @patch("src.config.cache.cache_get", new_callable=AsyncMock, return_value={"event_id": "123"})
    async def test_check_idempotency_key_hit(self, _):
        result = await cache_mod.check_idempotency_key("t1", "k1", "api_call")
        assert result == {"event_id": "123"}

    @patch("src.config.cache.cache_set", new_callable=AsyncMock)
    async def test_store_idempotency_response(self, mock_set):
        await cache_mod.store_idempotency_response("t1", "k1", "api_call", {"a": 1})
        mock_set.assert_awaited_once_with("idem:t1:k1:api_call", {"a": 1}, ttl_seconds=86400)
