"""Unit tests for Phase 4 RecommendationService."""

from datetime import timedelta
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

from service.config import CacheConfig, RateLimitConfig
from service.service import InMemoryCache, RateLimiter, RecommendationService


def test_inmemory_cache_stores_and_expires_entries(monkeypatch):
    cfg = CacheConfig(max_entries=2, ttl=timedelta(seconds=1))
    cache = InMemoryCache(config=cfg)

    cache.set("k1", {"v": 1})
    assert cache.get("k1") == {"v": 1}

    # Simulate expiry by patching datetime.utcnow
    with patch("service.service.datetime") as mock_dt:
        from datetime import datetime as real_dt

        mock_dt.utcnow.return_value = real_dt.utcnow() + timedelta(seconds=2)
        assert cache.get("k1") is None


def test_inmemory_cache_evicts_lru():
    cfg = CacheConfig(max_entries=2, ttl=timedelta(seconds=60))
    cache = InMemoryCache(config=cfg)

    cache.set("k1", {"v": 1})
    cache.set("k2", {"v": 2})
    cache.get("k1")  # k1 becomes most recently used
    cache.set("k3", {"v": 3})  # should evict k2

    assert cache.get("k1") == {"v": 1}
    assert cache.get("k2") is None
    assert cache.get("k3") == {"v": 3}


def test_rate_limiter_allows_within_window():
    cfg = RateLimitConfig(max_requests=2, window=timedelta(seconds=60))
    rl = RateLimiter(config=cfg)

    assert rl.allow("s1")
    assert rl.allow("s1")
    assert not rl.allow("s1")


def test_recommendation_service_uses_cache_and_rate_limit(monkeypatch):
    # Use small rate limit and cache
    cache_cfg = CacheConfig(max_entries=10, ttl=timedelta(seconds=60))
    rate_cfg = RateLimitConfig(max_requests=2, window=timedelta(seconds=60))

    cache = InMemoryCache(config=cache_cfg)
    rl = RateLimiter(config=rate_cfg)

    service = RecommendationService(cache=cache, rate_limiter=rl)

    fake_result: Dict = {"restaurants": [{"name": "Test"}], "explanation": "ok", "session_id": "s1"}

    with patch("service.service._llm_recommend") as mock_rec:
        mock_rec.return_value = fake_result

        # First call: miss, hits underlying
        r1 = service.recommend("hello", session_id="s1", limit=5)
        assert r1 == fake_result
        assert mock_rec.call_count == 1

        # Second call with same key: should be served from cache
        r2 = service.recommend("hello", session_id="s1", limit=5)
        assert r2 == fake_result
        assert mock_rec.call_count == 1  # not incremented

        # Third call: rate limit exceeded
        with pytest.raises(RuntimeError):
            service.recommend("another", session_id="s1", limit=5)

