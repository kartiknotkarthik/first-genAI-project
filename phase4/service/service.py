from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .config import CacheConfig, RateLimitConfig, get_cache_config, get_rate_limit_config

# Allow importing orchestrator from phase3 when running from phase4
import sys
from pathlib import Path

_phase3 = Path(__file__).resolve().parent.parent.parent / "phase3"
if _phase3.exists() and str(_phase3) not in sys.path:
    sys.path.insert(0, str(_phase3))

from orchestrator.orchestrator import recommend as _llm_recommend  # type: ignore  # noqa: E402
from orchestrator.orchestrator import refine as _llm_refine  # type: ignore  # noqa: E402

logger = logging.getLogger("zomato.service")


@dataclass
class _CacheEntry:
    value: Dict[str, Any]
    created_at: datetime


class InMemoryCache:
    """Very small LRU+TTL cache for recommendation responses."""

    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        self._config = config or get_cache_config()
        self._store: "OrderedDict[str, _CacheEntry]" = OrderedDict()

    def _is_expired(self, entry: _CacheEntry, now: datetime) -> bool:
        return now - entry.created_at > self._config.ttl

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow()
        entry = self._store.get(key)
        if not entry:
            return None
        if self._is_expired(entry, now):
            # Remove expired entry
            self._store.pop(key, None)
            return None
        # Mark as recently used
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Dict[str, Any]) -> None:
        now = datetime.utcnow()
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = _CacheEntry(value=value, created_at=now)
        # Evict oldest if over capacity
        while len(self._store) > self._config.max_entries:
            self._store.popitem(last=False)


class RateLimiter:
    """Simple in-memory per-session rate limiter."""

    def __init__(self, config: Optional[RateLimitConfig] = None) -> None:
        self._config = config or get_rate_limit_config()
        # session_id -> (first_request_time, count)
        self._state: Dict[str, Tuple[datetime, int]] = {}

    def allow(self, session_id: str) -> bool:
        now = datetime.utcnow()
        window = self._config.window
        first, count = self._state.get(session_id, (now, 0))

        if now - first > window:
            # Reset window
            self._state[session_id] = (now, 1)
            return True

        if count < self._config.max_requests:
            self._state[session_id] = (first, count + 1)
            return True

        return False


class RecommendationService:
    """
    Phase 4 service layer adding caching, rate limiting, and logging
    over the Phase 3 orchestrator's recommend/refine functions.
    """

    def __init__(
        self,
        cache: Optional[InMemoryCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self._cache = cache or InMemoryCache()
        self._rate_limiter = rate_limiter or RateLimiter()

    @staticmethod
    def _cache_key(user_message: str, session_id: Optional[str], limit: int) -> str:
        base = {
            "user_message": user_message.strip(),
            "session_id": session_id or "default",
            "limit": limit,
        }
        raw = json.dumps(base, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _check_rate_limit(self, session_id: str) -> None:
        if not self._rate_limiter.allow(session_id):
            logger.warning("Rate limit exceeded for session_id=%s", session_id)
            raise RuntimeError("Rate limit exceeded. Please wait before sending more requests.")

    def recommend(
        self,
        user_message: str,
        *,
        session_id: Optional[str] = None,
        db_url: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """High-level recommend with caching, rate limiting, and logging."""
        sid = session_id or "default"
        self._check_rate_limit(sid)

        key = self._cache_key(user_message, sid, limit)
        cached = self._cache.get(key)
        if cached is not None:
            logger.info("Cache hit for session_id=%s", sid)
            return cached

        logger.info("Cache miss for session_id=%s; calling LLM orchestrator", sid)
        result = _llm_recommend(
            user_message,
            session_id=sid,
            db_url=db_url,
            limit=limit,
        )
        self._cache.set(key, result)
        return result

    def refine(
        self,
        user_message: str,
        *,
        session_id: str,
        db_url: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """High-level refine with rate limiting and logging (no cache by default)."""
        self._check_rate_limit(session_id)
        logger.info("Refine for session_id=%s", session_id)
        return _llm_refine(
            user_message,
            session_id=session_id,
            db_url=db_url,
            limit=limit,
        )

