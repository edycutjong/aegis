"""Tests for app.cache.semantic."""

import json
from unittest.mock import AsyncMock, patch

from app.cache.semantic import SemanticCache


class TestMakeKey:
    """Verify deterministic, case-insensitive cache key generation."""

    def test_deterministic(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        key1 = cache._make_key("Hello World")
        key2 = cache._make_key("Hello World")
        assert key1 == key2

    def test_case_insensitive(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        key_upper = cache._make_key("Hello World")
        key_lower = cache._make_key("  hello world  ")
        assert key_upper == key_lower

    def test_key_prefix(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        key = cache._make_key("test query")
        assert key.startswith("aegis:cache:")
        # 16-char hex hash after prefix
        assert len(key) == len("aegis:cache:") + 16


class TestSemanticCacheGracefulDegradation:
    """Cache should work gracefully without Redis."""

    async def test_get_returns_none_without_redis(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        result = await cache.get("some query")
        assert result is None
        assert cache.stats["misses"] == 1

    async def test_set_noops_without_redis(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        # Should not raise
        await cache.set("some query", {"response": "cached"})

    def test_get_stats_initial_state(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 0, "misses": 0}

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_requests"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["connected"] is False

    def test_get_stats_after_misses(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None
        cache.stats = {"hits": 3, "misses": 7}

        stats = cache.get_stats()
        assert stats["total_requests"] == 10
        assert stats["hit_rate_percent"] == 30.0


class TestSemanticCacheWithMockedRedis:
    """Test cache operations with a mocked Redis client."""

    async def test_get_cache_hit(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.stats = {"hits": 0, "misses": 0}
        cache.redis = AsyncMock()
        cached_data = {"final_response": "Your balance is $100"}
        cache.redis.get = AsyncMock(return_value=json.dumps(cached_data))

        result = await cache.get("what is my balance")
        assert result == cached_data
        assert cache.stats["hits"] == 1

    async def test_get_cache_miss(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.stats = {"hits": 0, "misses": 0}
        cache.redis = AsyncMock()
        cache.redis.get = AsyncMock(return_value=None)

        result = await cache.get("what is my balance")
        assert result is None
        assert cache.stats["misses"] == 1

    async def test_get_redis_error_graceful(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.stats = {"hits": 0, "misses": 0}
        cache.redis = AsyncMock()
        cache.redis.get = AsyncMock(side_effect=Exception("Connection lost"))

        result = await cache.get("some query")
        assert result is None
        assert cache.stats["misses"] == 1

    async def test_set_stores_data(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.stats = {"hits": 0, "misses": 0}
        cache.ttl = 3600
        cache.redis = AsyncMock()
        cache.redis.set = AsyncMock()

        await cache.set("query", {"response": "answer"})
        cache.redis.set.assert_called_once()

    async def test_set_redis_error_graceful(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.stats = {"hits": 0, "misses": 0}
        cache.ttl = 3600
        cache.redis = AsyncMock()
        cache.redis.set = AsyncMock(side_effect=Exception("Connection lost"))

        # Should not raise
        await cache.set("query", {"response": "answer"})


class TestSemanticCacheConnectClose:
    """Test connect and close methods."""

    async def test_connect_success(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis_url = "redis://localhost:6379"

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch("app.cache.semantic.redis.from_url", return_value=mock_redis):
            await cache.connect()
        assert cache.redis is mock_redis

    async def test_connect_failure(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis_url = "redis://nonexistent:6379"

        with patch("app.cache.semantic.redis.from_url", side_effect=Exception("Connection refused")):
            await cache.connect()
        assert cache.redis is None

    async def test_close_with_redis(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = AsyncMock()
        cache.redis.close = AsyncMock()

        await cache.close()
        cache.redis.close.assert_called_once()

    async def test_close_without_redis(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = None

        # Should not raise
        await cache.close()

    def test_get_stats_connected(self):
        cache = SemanticCache.__new__(SemanticCache)
        cache.redis = AsyncMock()  # Non-None means connected
        cache.stats = {"hits": 5, "misses": 5}

        stats = cache.get_stats()
        assert stats["connected"] is True
        assert stats["hit_rate_percent"] == 50.0


class TestGetCacheSingleton:
    """get_cache() should return the same instance."""

    async def test_returns_singleton(self):
        import app.cache.semantic as cache_mod
        cache_mod._cache = None

        with patch.object(SemanticCache, "connect", new_callable=AsyncMock):
            c1 = await cache_mod.get_cache()
            c2 = await cache_mod.get_cache()
            assert c1 is c2

        cache_mod._cache = None

