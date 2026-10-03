"""Public product catalog API tests."""

from datetime import datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from src.models.product import Product
from src.services import product_catalog_cache as product_catalog_cache_module


def _product(
    sku: str,
    created_at: datetime,
    *,
    product_id: UUID,
    is_active: bool = True,
) -> Product:
    return Product(
        id=product_id,
        name=f"Product {sku}",
        description=f"Description for {sku}",
        sku=sku,
        price=1299,
        stock_quantity=8,
        max_purchase_quantity=3,
        is_active=is_active,
        created_at=created_at,
    )


class TestPublicProductCatalog:
    async def test_list_returns_active_products_newest_first_with_public_fields(
        self, test_client: AsyncClient, test_db
    ):
        same_time = datetime(2026, 9, 1)
        test_db.add_all(
            [
                _product(
                    "TIE-LOW",
                    same_time,
                    product_id=UUID("00000000-0000-0000-0000-000000000001"),
                ),
                _product(
                    "TIE-HIGH",
                    same_time,
                    product_id=UUID("00000000-0000-0000-0000-000000000002"),
                ),
                _product(
                    "NEWEST",
                    datetime(2026, 9, 2),
                    product_id=UUID("00000000-0000-0000-0000-000000000003"),
                ),
                _product(
                    "INACTIVE",
                    datetime(2026, 9, 3),
                    product_id=UUID("00000000-0000-0000-0000-000000000004"),
                    is_active=False,
                ),
            ]
        )
        await test_db.flush()

        response = await test_client.get("/api/v1/products")

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 24
        assert [item["sku"] for item in data["items"]] == [
            "NEWEST",
            "TIE-HIGH",
            "TIE-LOW",
        ]
        assert data["total"] == 3
        assert set(data["items"][0]) == {
            "id",
            "name",
            "description",
            "category",
            "brand",
            "sku",
            "price",
            "list_price",
            "image_url",
            "image_alt",
            "image_source_url",
            "image_creator",
            "image_license",
            "image_license_url",
            "image_sha256",
            "specifications",
            "stock_quantity",
            "max_purchase_quantity",
            "delivery",
            "highlights",
            "image_gallery",
        }
        assert data["items"][0]["category"] is None
        assert data["items"][0]["price"] == 1299
        assert "is_active" not in data["items"][0]

    async def test_list_honors_skip_and_limit(self, test_client: AsyncClient, test_db):
        test_db.add_all(
            [
                _product(
                    f"PAGE-{index}",
                    datetime(2026, 9, index),
                    product_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
                )
                for index in range(1, 4)
            ]
        )
        await test_db.flush()

        response = await test_client.get("/api/v1/products?skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 1
        assert data["limit"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["sku"] == "PAGE-2"

    async def test_list_accepts_maximum_page_size(self, test_client: AsyncClient):
        response = await test_client.get("/api/v1/products?limit=100")

        assert response.status_code == 200
        assert response.json()["limit"] == 100

    async def test_list_returns_empty_items_when_catalog_is_empty(self, test_client: AsyncClient):
        response = await test_client.get("/api/v1/products")

        assert response.status_code == 200
        assert response.json() == {"items": [], "skip": 0, "limit": 24, "total": 0}

    async def test_search_filters_sorts_and_returns_total(self, test_client: AsyncClient, test_db):
        newest = _product(
            "CATALOG-LAPTOP-2",
            datetime(2026, 9, 2),
            product_id=UUID("00000000-0000-0000-0000-000000000012"),
        )
        newest.name = "Northstar 14 Laptop"
        newest.category = "laptops"
        newest.brand = "Northstar"
        newest.price = 5_500_000
        newest.list_price = 6_000_000
        newest.image_url = "/products/northstar-14.jpg"
        newest.image_alt = "Silver 14-inch laptop, open on a desk"
        newest.image_source_url = "https://images.example.test/northstar-14"
        newest.image_creator = "Catalog Studio"
        newest.image_license = "CC BY 4.0"
        newest.image_license_url = "https://creativecommons.org/licenses/by/4.0/"
        newest.specifications = {"memory": "16 GB", "storage": "512 GB"}
        older = _product(
            "CATALOG-LAPTOP-1",
            datetime(2026, 9, 1),
            product_id=UUID("00000000-0000-0000-0000-000000000011"),
        )
        older.name = "Northstar 13 Laptop"
        older.category = "laptops"
        older.price = 4_500_000
        phone = _product(
            "CATALOG-PHONE",
            datetime(2026, 9, 3),
            product_id=UUID("00000000-0000-0000-0000-000000000013"),
        )
        phone.name = "Northstar Phone"
        phone.category = "phones"
        test_db.add_all([newest, older, phone])
        await test_db.flush()

        response = await test_client.get(
            "/api/v1/products?q=laptop&category=laptops&max_price_minor=6000000"
            "&in_stock_only=true&sort=price_asc&skip=0&limit=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1
        assert data["items"][0]["sku"] == "CATALOG-LAPTOP-1"
        assert data["items"][0]["brand"] is None
        assert data["items"][0]["image_url"] is None

        detail = await test_client.get(f"/api/v1/products/{newest.id}")
        assert detail.status_code == 200
        detail_data = detail.json()
        assert detail_data["brand"] == "Northstar"
        assert detail_data["list_price"] == 6_000_000
        assert detail_data["image_creator"] == "Catalog Studio"
        assert detail_data["image_license"] == "CC BY 4.0"
        assert detail_data["specifications"] == {"memory": "16 GB", "storage": "512 GB"}

    async def test_list_filters_brand_and_subcategory_case_insensitively(
        self, test_client: AsyncClient, test_db
    ):
        matching = _product(
            "BRAND-SUBCATEGORY-MATCH",
            datetime(2026, 9, 2),
            product_id=UUID("00000000-0000-0000-0000-000000000021"),
        )
        matching.brand = "Northstar"
        matching.category = "laptops"
        matching.specifications = {"Subcategory": "student notebooks"}
        nonmatching = _product(
            "BRAND-SUBCATEGORY-OTHER",
            datetime(2026, 9, 1),
            product_id=UUID("00000000-0000-0000-0000-000000000022"),
        )
        nonmatching.brand = "Northstar"
        nonmatching.category = "laptops"
        nonmatching.specifications = {"Subcategory": "business notebooks"}
        test_db.add_all([matching, nonmatching])
        await test_db.flush()

        response = await test_client.get(
            "/api/v1/products?brand=NORTHSTAR&subcategory=STUDENT%20NOTEBOOKS"
        )

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert [product["sku"] for product in response.json()["items"]] == [
            "BRAND-SUBCATEGORY-MATCH"
        ]

    async def test_detail_hides_inactive_and_missing_products(self, test_client: AsyncClient, test_db):
        inactive = _product(
            "CATALOG-INACTIVE",
            datetime(2026, 9, 1),
            product_id=UUID("00000000-0000-0000-0000-000000000014"),
            is_active=False,
        )
        test_db.add(inactive)
        await test_db.flush()

        response = await test_client.get(f"/api/v1/products/{inactive.id}")
        missing = await test_client.get(
            "/api/v1/products/00000000-0000-0000-0000-000000000099"
        )

        assert response.status_code == 404
        assert missing.status_code == 404

    @pytest.mark.parametrize(
        "query",
        [
            "min_price_minor=10&max_price_minor=9",
            "sort=untrusted",
            "category=unknown",
        ],
    )
    async def test_list_rejects_invalid_catalog_filters(self, test_client: AsyncClient, query: str):
        response = await test_client.get(f"/api/v1/products?{query}")

        assert response.status_code == 422

    async def test_list_falls_back_to_database_when_redis_is_unavailable(
        self, test_client: AsyncClient, test_db, monkeypatch
    ):
        test_db.add(
            _product(
                "REDIS-OFFLINE",
                datetime(2026, 9, 1),
                product_id=UUID("00000000-0000-0000-0000-000000000005"),
            )
        )
        await test_db.flush()

        class UnavailableRedis:
            async def get(self, _key):
                raise RedisConnectionError("Redis unavailable")

        monkeypatch.setattr(
            product_catalog_cache_module.settings, "redis_url", "redis://unavailable.test/0"
        )
        monkeypatch.setattr(product_catalog_cache_module, "get_redis_client", UnavailableRedis)

        response = await test_client.get("/api/v1/products")

        assert response.status_code == 200
        assert [item["sku"] for item in response.json()["items"]] == ["REDIS-OFFLINE"]

    @pytest.mark.parametrize(
        "query",
        ["skip=-1", "limit=0", "limit=101"],
    )
    async def test_list_rejects_invalid_pagination(self, test_client: AsyncClient, query: str):
        response = await test_client.get(f"/api/v1/products?{query}")

        assert response.status_code == 422
