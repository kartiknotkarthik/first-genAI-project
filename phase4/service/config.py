from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class RateLimitConfig:
    """Simple per-session rate limit configuration."""

    max_requests: int = 20
    window: timedelta = timedelta(minutes=1)


@dataclass(frozen=True)
class CacheConfig:
    """In-memory cache configuration."""

    max_entries: int = 256
    ttl: timedelta = timedelta(minutes=5)


def get_rate_limit_config() -> RateLimitConfig:
    """Read rate-limit config from env (optional) with safe defaults."""
    max_requests = int(os.environ.get("ZSVC_RATE_MAX_REQUESTS", "20"))
    window_seconds = int(os.environ.get("ZSVC_RATE_WINDOW_SECONDS", "60"))
    return RateLimitConfig(max_requests=max_requests, window=timedelta(seconds=window_seconds))


def get_cache_config() -> CacheConfig:
    """Read cache config from env (optional) with safe defaults."""
    max_entries = int(os.environ.get("ZSVC_CACHE_MAX_ENTRIES", "256"))
    ttl_seconds = int(os.environ.get("ZSVC_CACHE_TTL_SECONDS", "300"))
    return CacheConfig(max_entries=max_entries, ttl=timedelta(seconds=ttl_seconds))

