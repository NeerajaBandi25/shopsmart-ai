"""Rate limiting module for login endpoint protection."""

import logging
import time
from collections import defaultdict
from hashlib import sha256
from threading import Lock
from typing import Callable, Optional
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from src.core.config import settings
from src.core.exceptions import AppException
from src.core.observability import request_id_context

_SHARED_LIMITER_ENVIRONMENTS = {"prod", "production", "stage", "staging"}
_logger = logging.getLogger("shopsmart.rate_limiter")

_RESERVE_ATTEMPT_SCRIPT = """
local now = tonumber(ARGV[1])
local cutoff = now - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
    return 1
end
redis.call('ZADD', KEYS[1], now, ARGV[4])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
return 0
"""


def _shared_limiter_required() -> bool:
    return settings.app_env.strip().lower() in _SHARED_LIMITER_ENVIRONMENTS


def _require_shared_limiter() -> None:
    raise AppException(
        "Login protection is temporarily unavailable",
        503,
        "rate_limiter_unavailable",
    )


class RateLimiter:
    """Redis-backed limiter with local-only memory fallback."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 15 * 60,
        clock: Optional[Callable[[], float]] = None,
    ):
        """Initialize rate limiter.

        Args:
            max_attempts: Max failed attempts allowed in window
            window_seconds: Time window in seconds (default 15 minutes)
            clock: Injectable Unix-time source for deterministic window tests
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock or (lambda: time.time())
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._redis: Optional[Redis] = None
        self._redis_failure_category = "redis_not_configured" if not settings.redis_url else None
        self._redis_exception_type: Optional[str] = None
        self._shared_failure_reported = False
        self._shared_failure_lock = Lock()
        if settings.redis_url:
            try:
                self._redis = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            except (RedisError, ValueError) as exc:
                self._redis = None
                self._redis_failure_category = "redis_initialization_failed"
                self._redis_exception_type = type(exc).__name__

    @staticmethod
    def _redis_key(ip_address: str) -> str:
        ip_hash = sha256(ip_address.encode("utf-8")).hexdigest()
        return f"shopsmart:login-rate-limit:{ip_hash}"

    def _report_shared_limiter_failure(
        self, category: str, exception_type: Optional[str] = None
    ) -> None:
        if not _shared_limiter_required():
            return
        with self._shared_failure_lock:
            if self._shared_failure_reported:
                return
            self._shared_failure_reported = True
        fields = {
            "event": "shared_login_limiter_unavailable",
            "reason": category,
            "request_id": request_id_context.get(),
        }
        if exception_type:
            fields["exception_type"] = exception_type
        _logger.warning("shared_login_limiter_unavailable", extra=fields)

    def _disable_redis(self, failure: Optional[BaseException] = None) -> None:
        if self._redis is not None:
            try:
                self._redis.close()
            except RedisError:
                pass
            self._redis = None
        if failure is not None:
            self._redis_failure_category = "redis_operation_failed"
            self._redis_exception_type = type(failure).__name__
            self._report_shared_limiter_failure(
                self._redis_failure_category, self._redis_exception_type
            )

    def _ensure_fallback_allowed(self) -> None:
        if _shared_limiter_required():
            self._report_shared_limiter_failure(
                self._redis_failure_category or "redis_unavailable",
                self._redis_exception_type,
            )
            _require_shared_limiter()

    def check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP has exceeded rate limit.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if rate limit exceeded, False otherwise
        """
        now = self._clock()

        if self._redis is not None:
            try:
                key = self._redis_key(ip_address)
                # Reserve one of the allowed attempts in the same atomic Redis
                # operation that checks the limit. This closes the burst race
                # between the old ZCARD check and a later ZADD after bcrypt.
                result = self._redis.eval(
                    _RESERVE_ATTEMPT_SCRIPT,
                    1,
                    key,
                    now,
                    self.window_seconds,
                    self.max_attempts,
                    f"{now}:{uuid4().hex}",
                )
                return bool(result)
            except RedisError as exc:
                self._disable_redis(exc)

        self._ensure_fallback_allowed()
        # Clean old attempts outside the window
        self._attempts[ip_address] = [
            timestamp
            for timestamp in self._attempts[ip_address]
            if now - timestamp < self.window_seconds
        ]

        # Check if limit exceeded
        if len(self._attempts[ip_address]) >= self.max_attempts:
            return True

        return False

    def record_attempt(self, ip_address: str) -> None:
        """Record a failed login attempt.

        Args:
            ip_address: Client IP address
        """
        if self._redis is not None:
            try:
                # Redis-backed checks reserve atomically before authentication;
                # adding again here would count every failed login twice.
                return
            except RedisError as exc:
                self._disable_redis(exc)

        self._ensure_fallback_allowed()
        self._attempts[ip_address].append(self._clock())

    def reset_attempts(self, ip_address: str) -> None:
        """Reset attempts for IP (after successful login or timeout).

        Args:
            ip_address: Client IP address
        """
        if self._redis is not None:
            try:
                self._redis.delete(self._redis_key(ip_address))
            except RedisError as exc:
                self._disable_redis(exc)
        self._ensure_fallback_allowed()
        self._attempts[ip_address] = []


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_attempts=5,
    window_seconds=15 * 60,  # 15 minutes
)


def check_login_rate_limit(ip_address: str) -> bool:
    """Check if login should be rate limited.

    Args:
        ip_address: Client IP address

    Returns:
        bool: True if rate limited (should reject), False if allowed
    """
    return rate_limiter.check_rate_limit(ip_address)


def record_failed_attempt(ip_address: str) -> None:
    """Record a failed login attempt.

    Args:
        ip_address: Client IP address
    """
    rate_limiter.record_attempt(ip_address)


def record_successful_login(ip_address: str) -> None:
    """Reset rate limit on successful login.

    Args:
        ip_address: Client IP address
    """
    rate_limiter.reset_attempts(ip_address)
