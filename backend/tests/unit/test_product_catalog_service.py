"""Redis cache and database-fallback tests for the public product catalog."""

import json
from uuid import UUID

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.core import redis_client as redis_client_module
from src.schemas.product import ProductPageResponse
from src.services import product_catalog_cache as cache_module
from src.services import product_catalog_service as service_module
from src.services.product_catalog_cache import (
    CACHE_PREFIX,
    GENERATION_KEY,
    ProductCatalogCache,
    product_catalog_cache_key,
)
from src.services.product_catalog_service import ProductCatalogService


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}
        self.now = 0
        self.fail_get = False
        self.fail_set = False
        self.get_error = None
        self.fail_incr = False

    def _expire(self, key):
        if self.expirations.get(key, float("inf")) <= self.now:
            self.values.pop(key, None)
            self.expirations.pop(key, None)

    async def get(self, key):
        if self.get_error:
            raise self.get_error
        if self.fail_get:
            raise RedisConnectionError("Redis read failed")
        self._expire(key)
        return self.values.get(key)

    async def set(self, key, value, ex):
        if self.fail_set:
            raise RedisConnectionError("Redis write failed")
        self.values[key] = value
        self.expirations[key] = self.now + ex
        return True

    async def incr(self, key):
        if self.fail_incr:
            raise RedisConnectionError("Redis invalidation failed")
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value


class Repository:
    async def count_active_products(self):
        return 0


def _page(sku: str, skip: int = 0, limit: int = 24) -> ProductPageResponse:
    return ProductPageResponse(
        items=[
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": f"Product {sku}",
                "description": None,
                "category": None,
                "brand": "Test brand",
                "sku": sku,
                "price": 1299,
                "list_price": None,
                "image_url": None,
                "image_alt": None,
                "image_source_url": None,
                "image_creator": None,
                "image_license": None,
                "image_license_url": None,
                "image_sha256": None,
                "specifications": {},
                "stock_quantity": 8,
                "max_purchase_quantity": 3,
            }
        ],
        skip=skip,
        limit=limit,
        total=1,
    )


@pytest.fixture
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(cache_module.settings, "redis_url", "redis://cache.test/0")
    monkeypatch.setattr(cache_module.settings, "product_catalog_cache_ttl_seconds", 30)
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: client)
    return client


def test_product_catalog_cache_keys_include_namespace_generation_and_pagination():
    first_page = product_catalog_cache_key(skip=0, limit=24, generation="3")
    second_page = product_catalog_cache_key(skip=24, limit=24, generation="3")
    smaller_page = product_catalog_cache_key(skip=0, limit=12, generation="3")
    invalidated_page = product_catalog_cache_key(skip=0, limit=24, generation="4")

    assert first_page == f"{CACHE_PREFIX}:g3:skip:0:limit:24"
    assert len({first_page, second_page, smaller_page, invalidated_page}) == 4
    assert GENERATION_KEY == f"{CACHE_PREFIX}:generation"


async def test_cache_miss_reads_database_and_hit_skips_repository(fake_redis, monkeypatch):
    repository = Repository()
    calls = []

    async def get_products(*, skip, limit):
        calls.append((skip, limit))
        return [
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Product CACHED-1",
                "description": None,
                "category": None,
                "brand": "Test brand",
                "sku": "CACHED-1",
                "price": 1299,
                "list_price": None,
                "image_url": None,
                "image_alt": None,
                "image_source_url": None,
                "image_creator": None,
                "image_license": None,
                "image_license_url": None,
                "image_sha256": None,
                "specifications": {},
                "stock_quantity": 8,
                "max_purchase_quantity": 3,
            }
        ]

    repository.get_products = get_products

    async def count_active_products():
        return 1

    repository.count_active_products = count_active_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)
    service = ProductCatalogService(db=None)

    first = await service.list_products(skip=0, limit=24)
    assert first == _page("CACHED-1")
    assert calls == [(0, 24)]

    async def unexpected_database_read(**_kwargs):
        raise AssertionError("valid cache hit must not query the repository")

    repository.get_products = unexpected_database_read
    second = await service.list_products(skip=0, limit=24)

    assert second == first
    assert calls == [(0, 24)]
    cache_key = product_catalog_cache_key(skip=0, limit=24)
    assert fake_redis.expirations[cache_key] == 30
    assert fake_redis.values[cache_key] == json.dumps(
        first.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


async def test_distinct_pagination_parameters_populate_distinct_entries(fake_redis, monkeypatch):
    repository = Repository()
    calls = []

    async def get_products(*, skip, limit):
        calls.append((skip, limit))
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)
    service = ProductCatalogService(db=None)

    await service.list_products(skip=0, limit=24)
    await service.list_products(skip=24, limit=24)
    await service.list_products(skip=0, limit=12)

    assert calls == [(0, 24), (24, 24), (0, 12)]
    assert len([key for key in fake_redis.values if key.startswith(f"{CACHE_PREFIX}:g0:")]) == 3


async def test_cache_entries_expire_and_are_refilled(fake_redis, monkeypatch):
    repository = Repository()
    calls = 0

    async def get_products(*, skip, limit):
        nonlocal calls
        calls += 1
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)
    service = ProductCatalogService(db=None)

    await service.list_products(skip=0, limit=24)
    await service.list_products(skip=0, limit=24)
    fake_redis.now = 31
    await service.list_products(skip=0, limit=24)

    assert calls == 2
    assert fake_redis.expirations[product_catalog_cache_key(0, 24)] == 61


async def test_redis_read_failure_falls_back_to_database_without_a_write(fake_redis, monkeypatch):
    fake_redis.fail_get = True
    repository = Repository()
    repository.get_products = lambda **_kwargs: None

    async def get_products(**_kwargs):
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)
    page = await ProductCatalogService(db=None).list_products(skip=0, limit=24)

    assert page == _page_for_empty()
    assert not any(key.startswith(CACHE_PREFIX) for key in fake_redis.values)


async def test_redis_timeout_falls_back_to_database_without_a_write(fake_redis, monkeypatch):
    fake_redis.get_error = RedisTimeoutError("Redis read timed out")
    repository = Repository()

    async def get_products(**_kwargs):
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)

    page = await ProductCatalogService(db=None).list_products(skip=0, limit=24)

    assert page == _page_for_empty()
    assert not any(key.startswith(CACHE_PREFIX) for key in fake_redis.values)


async def test_redis_write_failure_does_not_fail_catalog_request(fake_redis, monkeypatch):
    fake_redis.fail_set = True
    repository = Repository()

    async def get_products(*, skip, limit):
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)

    page = await ProductCatalogService(db=None).list_products(skip=0, limit=24)

    assert page == _page_for_empty()


async def test_invalid_cached_payload_falls_back_and_replaces_it(fake_redis, monkeypatch):
    key = product_catalog_cache_key(skip=0, limit=24)
    fake_redis.values[key] = "not-json"
    repository = Repository()

    async def get_products(*, skip, limit):
        return []

    repository.get_products = get_products
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)

    page = await ProductCatalogService(db=None).list_products(skip=0, limit=24)

    assert page == _page_for_empty()
    assert ProductPageResponse.model_validate_json(fake_redis.values[key]) == page


async def test_repository_error_is_not_cached(fake_redis, monkeypatch):
    repository = Repository()

    async def fail_database_read(**_kwargs):
        raise RuntimeError("database read failed")

    repository.get_products = fail_database_read
    monkeypatch.setattr(service_module, "ProductRepository", lambda _db: repository)

    with pytest.raises(RuntimeError, match="database read failed"):
        await ProductCatalogService(db=None).list_products(skip=0, limit=24)

    assert not any(key.startswith(CACHE_PREFIX) for key in fake_redis.values)


async def test_invalidation_advances_generation_and_orphans_existing_pages(fake_redis):
    cache = ProductCatalogCache()
    await cache.set_page(0, 24, "0", _page("OLD"))

    await cache.invalidate()

    lookup = await cache.get_page(0, 24)
    assert lookup.page is None
    assert lookup.generation == "1"
    assert product_catalog_cache_key(0, 24, "0") in fake_redis.values


async def test_invalidation_failure_is_best_effort(fake_redis):
    fake_redis.fail_incr = True

    await ProductCatalogCache().invalidate()

    assert GENERATION_KEY not in fake_redis.values


async def test_async_redis_client_is_shared_and_closed(monkeypatch):
    class Client:
        closed = False

        async def aclose(self):
            self.closed = True

    client = Client()
    monkeypatch.setattr(redis_client_module, "_redis_client", None)
    monkeypatch.setattr(redis_client_module.settings, "redis_url", "redis://cache.test/0")
    monkeypatch.setattr(redis_client_module.Redis, "from_url", lambda *_args, **_kwargs: client)

    assert redis_client_module.get_redis_client() is client
    assert redis_client_module.get_redis_client() is client
    await redis_client_module.close_redis_client()

    assert client.closed
    assert redis_client_module._redis_client is None


def _page_for_empty() -> ProductPageResponse:
    return ProductPageResponse(items=[], skip=0, limit=24, total=0)
