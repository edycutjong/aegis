"""Tests for app.cache.semantic."""

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
