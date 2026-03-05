"""Semantic caching layer using Redis.

Flex 3: If a user asks the exact same question twice within an hour,
the backend serves the cached answer in ~50ms. Cost to the company: $0.00.
"""

import hashlib
import json

import redis.asyncio as redis
from app.config import get_settings


class SemanticCache:
    """Redis-backed semantic cache for agent responses."""

    def __init__(self):
        settings = get_settings()
        self.redis: redis.Redis | None = None
        self.redis_url = settings.redis_url
        self.ttl = settings.cache_ttl_seconds
        self.stats = {"hits": 0, "misses": 0}

    async def connect(self):
        """Initialize Redis connection."""
        try:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
        except Exception as e:
            print(f"[Cache] Redis connection failed: {e}. Running without cache.")
            self.redis = None

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    def _make_key(self, query: str) -> str:
        """Create a cache key from a normalized query."""
        normalized = query.strip().lower()
        query_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"aegis:cache:{query_hash}"

    async def get(self, query: str) -> dict | None:
        """Look up a cached response for a query.

        Returns None on cache miss, or the cached response dict on hit.
        """
        if not self.redis:
            self.stats["misses"] += 1
            return None

        try:
            key = self._make_key(query)
            cached = await self.redis.get(key)

            if cached:
                self.stats["hits"] += 1
                return json.loads(cached)

            self.stats["misses"] += 1
            return None
        except Exception:
            self.stats["misses"] += 1
            return None

    async def set(self, query: str, response: dict):
        """Cache an agent response."""
        if not self.redis:
            return

        try:
            key = self._make_key(query)
            await self.redis.set(
                key,
                json.dumps(response, default=str),
                ex=self.ttl,
            )
        except Exception as e:
            print(f"[Cache] Failed to cache: {e}")

    async def clear(self) -> int:
        """Clear all cached responses and reset stats.

        Returns the number of keys deleted.
        """
        deleted = 0
        if self.redis:
            try:
                cursor = "0"
                while cursor:
                    cursor, keys = await self.redis.scan(
                        cursor=cursor, match="aegis:cache:*", count=100
                    )
                    if keys:
                        deleted += await self.redis.delete(*keys)
                    if cursor == "0":
                        break
            except Exception as e:
                print(f"[Cache] Failed to clear: {e}")
        self.stats = {"hits": 0, "misses": 0}
        return deleted

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 1),
            "connected": self.redis is not None,
        }


# Singleton
_cache: SemanticCache | None = None

async def get_cache() -> SemanticCache:
    """Get or create the cache singleton."""
    global _cache
    if _cache is None:
        _cache = SemanticCache()
        await _cache.connect()
    return _cache
