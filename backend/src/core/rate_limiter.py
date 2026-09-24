"""Rate limiting module for login endpoint protection."""

import time
from collections import defaultdict
from hashlib import sha256
from typing import Callable, Optional
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from src.core.config import settings


class RateLimiter:
    """Rate limiter using in-memory store (fallback when Redis unavailable)."""

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
        if settings.redis_url:
            try:
                self._redis = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            except RedisError:
                self._redis = None

    @staticmethod
    def _redis_key(ip_address: str) -> str:
        ip_hash = sha256(ip_address.encode("utf-8")).hexdigest()
        return f"shopsmart:login-rate-limit:{ip_hash}"

    def _disable_redis(self) -> None:
        if self._redis is not None:
            self._redis.close()
            self._redis = None

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
                self._redis.zremrangebyscore(key, "-inf", now - self.window_seconds)
                return self._redis.zcard(key) >= self.max_attempts
            except RedisError:
                self._disable_redis()

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
                now = self._clock()
                key = self._redis_key(ip_address)
                self._redis.zadd(key, {f"{now}:{uuid4().hex}": now})
                self._redis.expire(key, self.window_seconds)
                return
            except RedisError:
                self._disable_redis()

        self._attempts[ip_address].append(self._clock())

    def reset_attempts(self, ip_address: str) -> None:
        """Reset attempts for IP (after successful login or timeout).

        Args:
            ip_address: Client IP address
        """
        if self._redis is not None:
            try:
                self._redis.delete(self._redis_key(ip_address))
            except RedisError:
                self._disable_redis()
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
