"""Public product catalog API tests."""

from datetime import datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from src.models.product import Product


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
        assert set(data["items"][0]) == {
            "id",
            "name",
            "description",
            "sku",
            "price",
            "stock_quantity",
            "max_purchase_quantity",
        }
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

    async def test_list_returns_empty_items_when_catalog_is_empty(
        self, test_client: AsyncClient
    ):
        response = await test_client.get("/api/v1/products")

        assert response.status_code == 200
        assert response.json() == {"items": [], "skip": 0, "limit": 24}

    @pytest.mark.parametrize(
        "query",
        ["skip=-1", "limit=0", "limit=101"],
    )
    async def test_list_rejects_invalid_pagination(
        self, test_client: AsyncClient, query: str
    ):
        response = await test_client.get(f"/api/v1/products?{query}")

        assert response.status_code == 422
