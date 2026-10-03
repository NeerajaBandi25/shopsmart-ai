from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.repositories.product_repository import ProductRepository


@pytest.mark.asyncio
async def test_development_preset_preserves_budget_and_stock(test_db):
    rows = [
        Product(name="Notebook", sku="DEV-MATCH", category="laptops", price=6000000,
                stock_quantity=2, specifications={"RAM": "16 GB RAM"}),
        Product(name="Small memory", sku="DEV-SMALL", category="laptops", price=5000000,
                stock_quantity=2, specifications={"RAM": "8 GB RAM"}),
        Product(name="Beyond budget", sku="DEV-EXPENSIVE", category="laptops", price=8000000,
                stock_quantity=2, specifications={"RAM": "32 GB RAM"}),
        Product(name="Sold out", sku="DEV-SOLD", category="laptops", price=6500000,
                stock_quantity=0, specifications={"RAM": "16 GB RAM"}),
    ]
    test_db.add_all(rows)
    await test_db.flush()
    matches, total = await ProductRepository(test_db).search_active_products_page(
        query_text="coding", category="laptops", max_price_cents=7000000, in_stock_only=True,
    )
    assert total == 1
    assert [product.sku for product in matches] == ["DEV-MATCH"]


@pytest.fixture(autouse=True)
def deduplicate_product_indexes_for_sqlite(monkeypatch):
    indexes = {index.name: index for index in Product.__table__.indexes}
    monkeypatch.setattr(Product.__table__, "indexes", set(indexes.values()))


def _product(
    sku: str,
    created_at: datetime,
    is_active: bool = True,
    category: str | None = None,
) -> Product:
    return Product(
        name=f"Product {sku}",
        description=None,
        category=category,
        sku=sku,
        price=100,
        stock_quantity=10,
        max_purchase_quantity=5,
        is_active=is_active,
        created_at=created_at,
    )


async def test_get_products_defaults_to_active_products_only(test_db: AsyncSession):
    test_db.add_all(
        [
            _product("ACTIVE-OLDER", datetime(2025, 1, 1)),
            _product("INACTIVE-NEWER", datetime(2025, 1, 2), is_active=False),
        ]
    )
    await test_db.flush()

    products = await ProductRepository(test_db).get_products()

    assert [product.sku for product in products] == ["ACTIVE-OLDER"]


async def test_get_products_can_include_inactive_products(test_db: AsyncSession):
    test_db.add_all(
        [
            _product("ACTIVE", datetime(2025, 1, 1)),
            _product("INACTIVE", datetime(2025, 1, 2), is_active=False),
        ]
    )
    await test_db.flush()

    products = await ProductRepository(test_db).get_products(active_only=False)

    assert [product.sku for product in products] == ["INACTIVE", "ACTIVE"]


async def test_get_products_orders_newest_first_and_applies_pagination(
    test_db: AsyncSession,
):
    test_db.add_all(
        [
            _product("OLDEST", datetime(2025, 1, 1)),
            _product("MIDDLE", datetime(2025, 1, 2)),
            _product("NEWEST", datetime(2025, 1, 3)),
        ]
    )
    await test_db.flush()
    repository = ProductRepository(test_db)

    all_products = await repository.get_products(active_only=False)
    page = await repository.get_products(skip=1, limit=1, active_only=False)

    assert [product.sku for product in all_products] == ["NEWEST", "MIDDLE", "OLDEST"]
    assert [product.sku for product in page] == ["MIDDLE"]


async def test_get_products_breaks_created_at_ties_by_id_descending(
    test_db: AsyncSession,
):
    created_at = datetime(2025, 1, 1)
    lower_id = UUID("00000000-0000-0000-0000-000000000001")
    higher_id = UUID("00000000-0000-0000-0000-000000000002")
    lower_id_product = _product("TIE-LOW", created_at)
    lower_id_product.id = lower_id
    higher_id_product = _product("TIE-HIGH", created_at)
    higher_id_product.id = higher_id
    test_db.add_all([lower_id_product, higher_id_product])
    await test_db.flush()

    products = await ProductRepository(test_db).get_products(active_only=False)

    assert [product.sku for product in products] == ["TIE-HIGH", "TIE-LOW"]


async def test_search_active_products_applies_price_stock_and_term_filters(test_db: AsyncSession):
    test_db.add_all(
        [
            Product(
                name="Wireless headphones",
                description="Over-ear audio",
                sku="HEADPHONES-IN",
                price=4999,
                stock_quantity=2,
                max_purchase_quantity=5,
                is_active=True,
            ),
            Product(
                name="Wireless headphones",
                description="Over-ear audio",
                sku="HEADPHONES-OUT",
                price=3999,
                stock_quantity=0,
                max_purchase_quantity=5,
                is_active=True,
            ),
            Product(
                name="Wireless headphones",
                description="Over-ear audio",
                sku="HEADPHONES-PRICE",
                price=5000,
                stock_quantity=3,
                max_purchase_quantity=5,
                is_active=True,
            ),
        ]
    )
    await test_db.flush()

    products = await ProductRepository(test_db).search_active_products(
        query_text="headphones", max_price_cents=4999, in_stock_only=True
    )

    assert [product.sku for product in products] == ["HEADPHONES-IN"]


async def test_category_filter_ignores_category_words_in_product_descriptions(
    test_db: AsyncSession,
):
    test_db.add_all(
        [
            Product(
                name="Laptops 1",
                description="Works with a USB-C charger",
                category="laptops",
                sku="CATEGORY-LAPTOP",
                price=5999999,
                stock_quantity=3,
                max_purchase_quantity=5,
                is_active=True,
            ),
            Product(
                name="USB-C Charger",
                description="Compatible with laptops",
                category="accessories",
                sku="CATEGORY-CHARGER",
                price=4999,
                stock_quantity=5,
                max_purchase_quantity=5,
                is_active=True,
            ),
        ]
    )
    await test_db.flush()

    products = await ProductRepository(test_db).search_active_products(
        query_text="laptops", category="laptops", max_price_cents=6_000_000
    )

    assert [product.sku for product in products] == ["CATEGORY-LAPTOP"]
    assert all(product.category == "laptops" and product.price <= 6_000_000 for product in products)


async def test_unknown_category_never_falls_back_to_text_search(test_db: AsyncSession):
    test_db.add(
        Product(
            name="Laptop Drone",
            description="A drone compatible with laptops",
            category="accessories",
            sku="UNKNOWN-CATEGORY",
            price=10000,
            stock_quantity=1,
            max_purchase_quantity=1,
            is_active=True,
        )
    )
    await test_db.flush()

    products = await ProductRepository(test_db).search_active_products(
        query_text="laptop", category="drones"
    )

    assert products == []
