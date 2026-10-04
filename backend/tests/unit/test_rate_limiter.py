"""Tests for Redis-backed rate limiting and in-memory fallback."""

import json
from concurrent.futures import ThreadPoolExecutor
import logging
from threading import Lock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.core import rate_limiter as rate_limiter_module
from src.core.exceptions import AppException
from src.core.observability import JsonLogFormatter, request_id_context
from src.core.rate_limiter import RateLimiter


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lock = Lock()

    def eval(self, script, number_of_keys, key, now, window, max_attempts, member):
        assert number_of_keys == 1
        assert script.index("ZREMRANGEBYSCORE") < script.index("ZCARD") < script.index("ZADD")
        # Models Redis EVAL serialization for prune/check/reserve as one op.
        with self.lock:
            entries = self.values.setdefault(key, {})
            cutoff = float(now) - float(window)
            self.values[key] = entries = {
                item: score for item, score in entries.items() if score > cutoff
            }
            if len(entries) >= int(max_attempts):
                return 1
            entries[member] = float(now)
            return 0

    def zremrangebyscore(self, key, _minimum, maximum):
        self.values.setdefault(key, {})
        self.values[key] = {
            member: score for member, score in self.values[key].items() if score > float(maximum)
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
        def eval(self, *_args):
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


def test_production_rate_limiter_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(rate_limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", None)
    limiter = RateLimiter(max_attempts=1, window_seconds=60)

    try:
        limiter.check_rate_limit("192.0.2.3")
    except AppException as error:
        assert error.status_code == 503
        assert error.error_code == "rate_limiter_unavailable"
    else:
        raise AssertionError("production must not fall back to a per-process limiter")


def test_production_rate_limiter_fails_closed_when_redis_fails(monkeypatch):
    class UnavailableRedis:
        def eval(self, *_args):
            raise RedisConnectionError("Redis unavailable")

        def close(self):
            return None

    monkeypatch.setattr(rate_limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", "redis://localhost")
    monkeypatch.setattr(
        rate_limiter_module.Redis,
        "from_url",
        lambda *_args, **_kwargs: UnavailableRedis(),
    )
    limiter = RateLimiter(max_attempts=1, window_seconds=60)

    try:
        limiter.check_rate_limit("192.0.2.4")
    except AppException as error:
        assert error.status_code == 503
        assert error.error_code == "rate_limiter_unavailable"
    else:
        raise AssertionError("production must reject logins when shared Redis is unavailable")


@pytest.mark.parametrize(
    ("redis_url", "expected_reason", "expected_exception_type"),
    [
        (None, "redis_not_configured", None),
        (
            "redis://sensitive-user:sensitive-password@private-host/0",
            "redis_operation_failed",
            "ConnectionError",
        ),
    ],
)
def test_production_shared_limiter_failure_logs_one_sanitized_warning(
    monkeypatch, caplog, redis_url, expected_reason, expected_exception_type
):
    class UnavailableRedis:
        def eval(self, *_args):
            raise RedisConnectionError("private host and password details")

        def close(self):
            return None

    monkeypatch.setattr(rate_limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", redis_url)
    if redis_url:
        monkeypatch.setattr(
            rate_limiter_module.Redis,
            "from_url",
            lambda *_args, **_kwargs: UnavailableRedis(),
        )
    logger = logging.getLogger("shopsmart.rate_limiter")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    limiter = RateLimiter(max_attempts=5, window_seconds=60)
    token = request_id_context.set("req-rate-limit-safe-1")
    try:
        with caplog.at_level(logging.WARNING, logger="shopsmart.rate_limiter"):
            for _ in range(2):
                with pytest.raises(AppException) as error:
                    limiter.check_rate_limit("203.0.113.99")
                assert error.value.status_code == 503
                assert error.value.error_code == "rate_limiter_unavailable"
    finally:
        request_id_context.reset(token)

    records = [record for record in caplog.records if record.name == "shopsmart.rate_limiter"]
    assert len(records) == 1
    assert records[0].event == "shared_login_limiter_unavailable"
    assert records[0].reason == expected_reason
    assert getattr(records[0], "exception_type", None) == expected_exception_type
    serialized = JsonLogFormatter().format(records[0])
    payload = json.loads(serialized)
    assert payload["request_id"] == "req-rate-limit-safe-1"
    for secret in (
        "203.0.113.99",
        "sensitive-user",
        "sensitive-password",
        "private-host",
        "private host and password details",
    ):
        assert secret not in serialized


def test_concurrent_production_limiter_failures_log_only_once(monkeypatch, caplog):
    monkeypatch.setattr(rate_limiter_module.settings, "app_env", "production")
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", None)
    logger = logging.getLogger("shopsmart.rate_limiter")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    limiter = RateLimiter(max_attempts=5, window_seconds=60)

    def check():
        try:
            limiter.check_rate_limit("203.0.113.100")
        except AppException as error:
            return error.status_code, error.error_code
        raise AssertionError("shared limiter failure must fail closed")

    with caplog.at_level(logging.WARNING, logger="shopsmart.rate_limiter"):
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _index: check(), range(64)))

    assert results == [(503, "rate_limiter_unavailable")] * 64
    records = [record for record in caplog.records if record.name == "shopsmart.rate_limiter"]
    assert len(records) == 1
    assert records[0].event == "shared_login_limiter_unavailable"
    assert "203.0.113.100" not in JsonLogFormatter().format(records[0])


def test_rate_limited_ip_does_not_affect_another_ip():
    limiter = RateLimiter(max_attempts=2, window_seconds=60, clock=lambda: 1000)
    limited_ip = "192.0.2.10"
    other_ip = "192.0.2.11"

    limiter.record_attempt(limited_ip)
    limiter.record_attempt(limited_ip)

    assert limiter.check_rate_limit(limited_ip) is True
    assert limiter.check_rate_limit(other_ip) is False


def test_redis_check_atomically_reserves_exactly_five_concurrent_attempts(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(rate_limiter_module.settings, "redis_url", "redis://localhost")
    monkeypatch.setattr(rate_limiter_module.Redis, "from_url", lambda *_args, **_kwargs: client)
    limiter = RateLimiter(max_attempts=5, window_seconds=60, clock=lambda: 1000)

    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: limiter.check_rate_limit("192.0.2.20"), range(64)))

    assert results.count(False) == 5
    assert results.count(True) == 59
    assert len(client.values[limiter._redis_key("192.0.2.20")]) == 5
