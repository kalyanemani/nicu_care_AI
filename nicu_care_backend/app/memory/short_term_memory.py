"""
Short-Term Multi-Agent Memory:
Redis-backed turn buffer, shared multi-agent scratchpad,
uncommitted observations, and semantic cache with thread-safe in-memory fallback.
"""
import os
import json
import time
import threading
from typing import Dict, List, Any, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class InMemoryRedisFallback:
    """Thread-safe, TTL-aware in-memory Redis emulator."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            self._store[key] = value
            if ex:
                self._expiry[key] = time.time() + ex
            elif key in self._expiry:
                del self._expiry[key]
            return True

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
            return self._store.get(key)

    def delete(self, *keys: str) -> int:
        with self._lock:
            count = 0
            for k in keys:
                if k in self._store:
                    del self._store[k]
                    self._expiry.pop(k, None)
                    count += 1
            return count

    def keys(self, pattern: str = "*") -> List[str]:
        with self._lock:
            now = time.time()
            valid_keys = []
            for k in list(self._store.keys()):
                if k in self._expiry and now > self._expiry[k]:
                    del self._store[k]
                    del self._expiry[k]
                else:
                    valid_keys.append(k)
            return valid_keys

    def ttl(self, key: str) -> int:
        with self._lock:
            if key not in self._expiry:
                return -1 if key in self._store else -2
            remaining = int(self._expiry[key] - time.time())
            return max(0, remaining)


class ShortTermMemory:
    """
    Manages short-term operational state across the multi-agent graph:
      - Live session turn buffer (sliding conversation history)
      - Shared working scratchpad between LangGraph nodes (Triage, Math, Critic)
      - Uncommitted observations pending clinician verification
      - High-speed query semantic cache
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self.is_real_redis = False

        if REDIS_AVAILABLE:
            try:
                r = redis.Redis.from_url(self.redis_url, decode_responses=True, socket_timeout=0.5)
                r.ping()
                self.client = r
                self.is_real_redis = True
            except Exception:
                self.client = InMemoryRedisFallback()
        else:
            self.client = InMemoryRedisFallback()

    # ── 1. Live Session Turn Buffer ──────────────────────────────────────
    def append_turn(
        self,
        baby_id: str,
        user_query: str,
        agent_response: str,
        intent: str,
        ttl_seconds: int = 7200
    ):
        """Appends a conversation turn to the baby's active session buffer."""
        key = f"session:{baby_id}:turns"
        raw = self.client.get(key)
        turns: List[Dict[str, Any]] = json.loads(raw) if raw else []

        turns.append({
            "timestamp": time.time(),
            "user_query": user_query,
            "agent_response": agent_response,
            "intent": intent,
        })
        # Keep last 10 turns
        turns = turns[-10:]
        self.client.set(key, json.dumps(turns), ex=ttl_seconds)

    def get_turn_buffer(self, baby_id: str) -> List[Dict[str, Any]]:
        """Returns the recent conversational turns from short-term memory."""
        key = f"session:{baby_id}:turns"
        raw = self.client.get(key)
        return json.loads(raw) if raw else []

    # ── 2. Shared Multi-Agent Scratchpad ─────────────────────────────────
    def write_scratchpad(self, baby_id: str, node_name: str, observation: str):
        """Allows an agent node (e.g. triage or math) to post findings before critic synthesis."""
        key = f"scratchpad:{baby_id}"
        raw = self.client.get(key)
        pad: Dict[str, str] = json.loads(raw) if raw else {}
        pad[node_name] = observation
        self.client.set(key, json.dumps(pad), ex=1800)

    def read_scratchpad(self, baby_id: str) -> Dict[str, str]:
        """Reads all active multi-agent scratchpad observations."""
        key = f"scratchpad:{baby_id}"
        raw = self.client.get(key)
        return json.loads(raw) if raw else {}

    def clear_scratchpad(self, baby_id: str):
        """Clears scratchpad after turn completion."""
        self.client.delete(f"scratchpad:{baby_id}")

    # ── 3. High-Speed Semantic Cache ─────────────────────────────────────
    def get_cached_response(self, normalized_query: str) -> Optional[Dict[str, Any]]:
        key = f"cache:query:{normalized_query}"
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set_cached_response(self, normalized_query: str, response: Dict[str, Any], ttl: int = 300):
        key = f"cache:query:{normalized_query}"
        self.client.set(key, json.dumps(response), ex=ttl)

    # ── 4. Telemetry / Inspector Helpers ─────────────────────────────────
    def get_all_keys(self) -> List[Dict[str, Any]]:
        """Lists active keys, type, and remaining TTL for the Streamlit Inspector."""
        keys = self.client.keys("*")
        result = []
        for k in keys:
            ttl = self.client.ttl(k) if hasattr(self.client, "ttl") else -1
            val = self.client.get(k)
            preview = str(val)[:80] + "..." if val and len(str(val)) > 80 else str(val)
            result.append({
                "key": k,
                "ttl_seconds": ttl,
                "preview": preview,
            })
        return result


# Global Singleton Short-Term Memory
short_term_memory = ShortTermMemory()
