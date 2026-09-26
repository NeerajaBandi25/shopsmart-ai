"""Transactional checkout service tests."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.models.order import Order
from src.models.product import Product
from src.models.user import User
from src.repositories.order_repository import OrderRepository
from src.services.order_service import OrderService


class TestOrderService:
    async def test_checkout_snapshots_prices_and_replays_same_payload(
        self, test_db
    ):
        user_id = uuid4()
        product_id = uuid4()
        product = Product(
            id=product_id,
            name="Original name",
            sku="SNAPSHOT-1",
            price=1299,
            stock_quantity=6,
            max_purchase_quantity=4,
            is_active=True,
        )
        test_db.add_all(
            [
                User(id=user_id, email="snapshot@example.com", password_hash="unused"),
                product,
            ]
        )
        await test_db.commit()

        service = OrderService(test_db)
        first = await service.checkout(user_id, "retry-key", [(product_id, 2)])
        product.name = "Renamed later"
        product.price = 2500
        await test_db.commit()
        replay = await service.checkout(user_id, "retry-key", [(product_id, 2)])

        assert replay.id == first.id
        assert replay.total_cents == 2598
        assert replay.items[0].product_name == "Original name"
        assert replay.items[0].product_sku == "SNAPSHOT-1"
        assert replay.items[0].unit_price_cents == 1299
        assert replay.items[0].line_total_cents == 2598
        assert product.stock_quantity == 4

        with pytest.raises(Exception, match="different checkout payload"):
            await service.checkout(user_id, "retry-key", [(product_id, 1)])

    async def test_rejects_duplicate_lines_and_limits_without_mutation(self, test_db):
        user_id = uuid4()
        product_id = uuid4()
        low_stock_id = uuid4()
        test_db.add_all(
            [
                User(id=user_id, email="limits@example.com", password_hash="unused"),
                Product(
                    id=product_id,
                    name="Limited",
                    sku="LIMIT-1",
                    price=50,
                    stock_quantity=3,
                    max_purchase_quantity=2,
                    is_active=True,
                ),
                Product(
                    id=low_stock_id,
                    name="Low stock",
                    sku="LOW-STOCK-1",
                    price=75,
                    stock_quantity=1,
                    max_purchase_quantity=4,
                    is_active=True,
                ),
            ]
        )
        await test_db.commit()

        with pytest.raises(Exception, match="Product lines must be unique"):
            await OrderService(test_db).checkout(
                user_id, "duplicate", [(product_id, 1), (product_id, 1)]
            )
        await test_db.rollback()
        with pytest.raises(Exception, match="Quantity exceeds the limit"):
            await OrderService(test_db).checkout(user_id, "limit", [(product_id, 3)])
        await test_db.rollback()
        with pytest.raises(Exception, match="Insufficient stock"):
            await OrderService(test_db).checkout(user_id, "stock", [(low_stock_id, 2)])
        await test_db.rollback()

        stock = await test_db.scalar(
            select(Product.stock_quantity).where(Product.id == product_id)
        )
        assert stock == 3

    async def test_late_failure_rolls_back_all_stock_and_orders(
        self, test_db, fresh_test_session, monkeypatch
    ):
        user_id = uuid4()
        first_id = uuid4()
        second_id = uuid4()
        first = Product(
            id=first_id,
            name="First",
            sku="ROLLBACK-1",
            price=100,
            stock_quantity=5,
            max_purchase_quantity=5,
            is_active=True,
        )
        second = Product(
            id=second_id,
            name="Second",
            sku="ROLLBACK-2",
            price=200,
            stock_quantity=5,
            max_purchase_quantity=5,
            is_active=True,
        )
        test_db.add_all(
            [User(id=user_id, email="rollback@example.com", password_hash="unused"), first, second]
        )
        await test_db.commit()

        original_decrement = OrderRepository.decrement_stock
        calls = 0

        async def fail_on_second_decrement(repository, product_id, quantity):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated late stock-write failure")
            return await original_decrement(repository, product_id, quantity)

        monkeypatch.setattr(OrderRepository, "decrement_stock", fail_on_second_decrement)
        with pytest.raises(RuntimeError, match="simulated late stock-write failure"):
            await OrderService(test_db).checkout(
                user_id,
                "late-failure",
                [(first_id, 2), (second_id, 3)],
            )

        await test_db.rollback()
        first_stock = await fresh_test_session.scalar(
            select(Product.stock_quantity).where(Product.id == first_id)
        )
        second_stock = await fresh_test_session.scalar(
            select(Product.stock_quantity).where(Product.id == second_id)
        )
        order_count = await fresh_test_session.scalar(select(func.count()).select_from(Order))
        assert (first_stock, second_stock, order_count) == (5, 5, 0)