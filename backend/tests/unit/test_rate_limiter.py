"""Tests for Redis-backed rate limiting and in-memory fallback."""

from redis.exceptions import ConnectionError as RedisConnectionError

from src.core import rate_limiter as rate_limiter_module
from src.core.rate_limiter import RateLimiter


class FakeRedis:
    def __init__(self):
        self.values = {}

    def zremrangebyscore(self, key, _minimum, maximum):
        self.values.setdefault(key, {})
        self.values[key] = {
            member: score
            for member, score in self.values[key].items()
            if score > float(maximum)
        }

    def zcard(self, key):
        return len(self.values.get(key, {}))

    def zadd(self, key, values):
        self.values.setdefault(key, {}).update(values)

    def expire(self, _key, _seconds):
        return True

    def delete(self, key):
        self.values.pop(key, None)

    def close(self):
        return None


def test_rate_limiter_uses_redis_and_resets(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", "redis://localhost")
    monkeypatch.setattr(rate_limiter_module.Redis, "from_url", lambda *_args, **_kwargs: client)
    limiter = RateLimiter(max_attempts=1, window_seconds=60)

    assert limiter.check_rate_limit("192.0.2.1") is False
    limiter.record_attempt("192.0.2.1")
    assert limiter.check_rate_limit("192.0.2.1") is True

    limiter.reset_attempts("192.0.2.1")

    assert limiter.check_rate_limit("192.0.2.1") is False


def test_rate_limiter_falls_back_to_memory_when_redis_fails(monkeypatch):
    class UnavailableRedis:
        def zremrangebyscore(self, *_args):
            raise RedisConnectionError("Redis unavailable")

        def close(self):
            return None

    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", "redis://localhost")
    monkeypatch.setattr(
        rate_limiter_module.Redis,
        "from_url",
        lambda *_args, **_kwargs: UnavailableRedis(),
    )
    limiter = RateLimiter(max_attempts=1, window_seconds=60)

    assert limiter.check_rate_limit("192.0.2.2") is False
    limiter.record_attempt("192.0.2.2")

    assert limiter.check_rate_limit("192.0.2.2") is True