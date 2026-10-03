"""Best-effort Redis cache for public product catalog pages."""

import json
from dataclasses import dataclass

from redis.exceptions import RedisError

from src.core.config import settings
from src.core.redis_client import get_redis_client
from src.schemas.product import ProductPageResponse

CACHE_PREFIX = "shopsmart:product-catalog:v2"
GENERATION_KEY = f"{CACHE_PREFIX}:generation"


@dataclass(frozen=True)
class CatalogCacheLookup:
    """A cache result and generation token safe to use for a later fill."""

    page: ProductPageResponse | None
    generation: str | None


def product_catalog_cache_key(skip: int, limit: int, generation: str = "0") -> str:
    """Build a namespaced key covering every current catalog query parameter."""
    return f"{CACHE_PREFIX}:g{generation}:skip:{skip}:limit:{limit}"


class ProductCatalogCache:
    """Cache validated catalog pages without making Redis availability mandatory."""

    async def get_page(self, skip: int, limit: int) -> CatalogCacheLookup:
        if not settings.redis_url:
            return CatalogCacheLookup(page=None, generation=None)

        try:
            client = get_redis_client()
            if client is None:
                return CatalogCacheLookup(page=None, generation=None)

            stored_generation = await client.get(GENERATION_KEY)
            generation = str(stored_generation) if stored_generation is not None else "0"
            payload = await client.get(product_catalog_cache_key(skip, limit, generation))
            current_generation = await client.get(GENERATION_KEY)
            current_generation = str(current_generation) if current_generation is not None else "0"
            if generation != current_generation:
                return CatalogCacheLookup(page=None, generation=current_generation)
        except (RedisError, ValueError):
            return CatalogCacheLookup(page=None, generation=None)

        if payload is None:
            return CatalogCacheLookup(page=None, generation=generation)

        try:
            page = ProductPageResponse.model_validate_json(payload)
        except (ValueError, TypeError):
            return CatalogCacheLookup(page=None, generation=generation)
        return CatalogCacheLookup(page=page, generation=generation)

    async def set_page(
        self,
        skip: int,
        limit: int,
        generation: str | None,
        page: ProductPageResponse,
    ) -> None:
        if generation is None or not settings.redis_url:
            return

        try:
            client = get_redis_client()
            if client is None:
                return
            payload = json.dumps(
                page.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            await client.set(
                product_catalog_cache_key(skip, limit, generation),
                payload,
                ex=settings.product_catalog_cache_ttl_seconds,
            )
        except (RedisError, TypeError, ValueError):
            return

    async def invalidate(self) -> None:
        """Advance the namespace so all existing catalog pages become unreachable."""
        if not settings.redis_url:
            return
        try:
            client = get_redis_client()
            if client is not None:
                await client.incr(GENERATION_KEY)
        except (RedisError, ValueError):
            return


async def invalidate_product_catalog_cache() -> None:
    """Best-effort invalidation after a committed product stock mutation."""
    await ProductCatalogCache().invalidate()
