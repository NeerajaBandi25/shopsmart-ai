"""Lazy async Redis client shared by backend services."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis | None:
    """Return the process-wide Redis client, or None when Redis is not configured."""
    global _redis_client
    if _redis_client is None and settings.redis_url:
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the process-wide async Redis client during application shutdown."""
    global _redis_client
    client, _redis_client = _redis_client, None
    if client is not None:
        try:
            await client.aclose()
        except RedisError:
            return
