"""Rate limiting module for login endpoint protection."""

import time
from collections import defaultdict
from typing import Optional

from src.core.config import settings


class RateLimiter:
    """Rate limiter using in-memory store (fallback when Redis unavailable)."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 15 * 60):
        """Initialize rate limiter.

        Args:
            max_attempts: Max failed attempts allowed in window
            window_seconds: Time window in seconds (default 15 minutes)
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP has exceeded rate limit.

        Args:
            ip_address: Client IP address

        Returns:
            bool: True if rate limit exceeded, False otherwise
        """
        now = time.time()

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
        self._attempts[ip_address].append(time.time())

    def reset_attempts(self, ip_address: str) -> None:
        """Reset attempts for IP (after successful login or timeout).

        Args:
            ip_address: Client IP address
        """
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
