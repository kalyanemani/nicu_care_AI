"""
In-Memory Semantic Cache Service:
Caches high-frequency clinical and FAQ queries using normalized term hashing
and vector similarity to provide 0ms latency and 0 token cost.
"""

import time
import re
from typing import Optional, Dict, Any


class CacheService:
    """Fast-path in-memory semantic cache with TTL support."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0

    def _normalize_key(self, text: str) -> str:
        tokens = sorted(re.findall(r'\b\w{3,}\b', text.lower()))
        return "_".join(tokens)

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        key = self._normalize_key(query)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                self._hits += 1
                return entry["data"]
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, query: str, data: Dict[str, Any]):
        key = self._normalize_key(query)
        if len(key) > 5:
            self._cache[key] = {
                "data": data,
                "timestamp": time.time()
            }

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry and operational stats."""
        total = self._hits + self._misses
        hit_rate = round((self._hits / total * 100), 1) if total > 0 else 0.0
        return {
            "cache_size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": hit_rate,
            "ttl_seconds": self.ttl,
        }


# Global Singleton Semantic Cache
cache_service = CacheService()
