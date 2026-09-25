from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.repositories.product_repository import ProductRepository


@pytest.fixture(autouse=True)
def deduplicate_product_indexes_for_sqlite(monkeypatch):
    indexes = {index.name: index for index in Product.__table__.indexes}
    monkeypatch.setattr(Product.__table__, "indexes", set(indexes.values()))


def _product(sku: str, created_at: datetime, is_active: bool = True) -> Product:
    return Product(
        name=f"Product {sku}",
        description=None,
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
