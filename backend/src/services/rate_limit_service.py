"""Cross-replica and development rate limiting for unauthenticated work."""

from __future__ import annotations

import hashlib
import threading
import time

from redis import Redis
from redis.exceptions import RedisError

from src.db.config import Settings, get_settings

_WINDOW_SECONDS = 60
_REDIS_INCREMENT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""
_CLIENT_LOCK = threading.Lock()
_REDIS_CLIENTS: dict[str, Redis] = {}
_LOCAL_LOCK = threading.Lock()
_LOCAL_WINDOW: int | None = None
_LOCAL_COUNTS: dict[str, int] = {}


class RateLimitExceededError(RuntimeError):
    """Raised when an unauthenticated caller exceeds the configured quota."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


class RateLimitUnavailableError(RuntimeError):
    """Raised when a configured shared limiter cannot safely admit work."""


def enforce_google_oauth_rate_limit(
    client_ip: str,
    settings: Settings | None = None,
) -> None:
    """Limit Google code exchanges by client IP over fixed one-minute windows."""
    active_settings = settings or get_settings()
    now = int(time.time())
    window = now // _WINDOW_SECONDS
    retry_after = _WINDOW_SECONDS - (now % _WINDOW_SECONDS)
    identity = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
    limit = active_settings.MAX_GOOGLE_OAUTH_ATTEMPTS_PER_IP_PER_MINUTE

    if active_settings.CELERY_BROKER_URL:
        key = f"ai-image-classifier:rate-limit:google-oauth:{window}:{identity}"
        try:
            count = int(
                _get_redis_client(active_settings.CELERY_BROKER_URL).eval(
                    _REDIS_INCREMENT_SCRIPT,
                    1,
                    key,
                    _WINDOW_SECONDS,
                )
            )
        except (RedisError, TypeError, ValueError) as exc:
            raise RateLimitUnavailableError("OAuth rate limiter is unavailable") from exc
    else:
        count = _increment_local_counter(identity, window)

    if count > limit:
        raise RateLimitExceededError(retry_after)


def _get_redis_client(redis_url: str) -> Redis:
    """Reuse one bounded Redis client per configured broker URL."""
    client = _REDIS_CLIENTS.get(redis_url)
    if client is None:
        with _CLIENT_LOCK:
            client = _REDIS_CLIENTS.get(redis_url)
            if client is None:
                client = Redis.from_url(
                    redis_url,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    decode_responses=True,
                )
                _REDIS_CLIENTS[redis_url] = client
    return client


def _increment_local_counter(identity: str, window: int) -> int:
    """Provide equivalent single-process behavior when Redis is not configured."""
    global _LOCAL_WINDOW
    with _LOCAL_LOCK:
        if _LOCAL_WINDOW != window:
            _LOCAL_COUNTS.clear()
            _LOCAL_WINDOW = window
        count = _LOCAL_COUNTS.get(identity, 0) + 1
        _LOCAL_COUNTS[identity] = count
        return count

