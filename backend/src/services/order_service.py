"""Transactional checkout and shopper-scoped order history."""

import hashlib
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, ConflictError
from src.models.order import Order, OrderItem
from src.repositories.order_repository import OrderRepository


class OrderService:
    """Apply checkout rules and own the durable transaction boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = OrderRepository(db)

    @staticmethod
    def _request_hash(items: list[tuple[UUID, int]]) -> str:
        canonical = sorted((str(product_id), quantity) for product_id, quantity in items)
        encoded = json.dumps(canonical, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _replay_or_conflict(order: Order, request_hash: str) -> Order:
        if order.request_hash != request_hash:
            raise ConflictError(
                "Idempotency key was already used with a different checkout payload",
                error_code="idempotency_conflict",
            )
        return order

    async def checkout(
        self, user_id: UUID, key: str, items: list[tuple[UUID, int]]
    ) -> Order:
        key = key.strip()
        if not key:
            raise AppException("Idempotency-Key is required", 400, "idempotency_key_required")
        if not items:
            raise AppException("At least one item is required", 400, "empty_order")
        product_ids = [product_id for product_id, _ in items]
        if len(product_ids) != len(set(product_ids)):
            raise AppException("Product lines must be unique", 422, "duplicate_product")
        if any(quantity < 1 for _, quantity in items):
            raise AppException("Quantities must be positive", 422, "invalid_quantity")

        request_hash = self._request_hash(items)
        try:
            async with self.db.begin_nested():
                existing = await self.repository.get_by_idempotency_key(user_id, key)
                if existing:
                    order = self._replay_or_conflict(existing, request_hash)
                else:
                    products = await self.repository.lock_products(product_ids)
                    # A competing request may have committed while this request waited on row locks.
                    existing = await self.repository.get_by_idempotency_key(user_id, key)
                    if existing:
                        order = self._replay_or_conflict(existing, request_hash)
                    else:
                        for product_id, quantity in items:
                            product = products.get(product_id)
                            if product is None:
                                raise AppException(
                                    "One or more products do not exist", 404, "product_not_found"
                                )
                            if not product.is_active:
                                raise ConflictError(
                                    f"Product {product.sku} is not available",
                                    error_code="product_unavailable",
                                )
                            if quantity > product.max_purchase_quantity:
                                raise AppException(
                                    f"Quantity exceeds the limit for {product.sku}",
                                    422,
                                    "purchase_limit_exceeded",
                                )
                            if quantity > product.stock_quantity:
                                raise ConflictError(
                                    f"Insufficient stock for {product.sku}",
                                    error_code="insufficient_stock",
                                )

                        total_cents = sum(
                            products[product_id].price * quantity
                            for product_id, quantity in items
                        )
                        order = Order(
                            user_id=user_id,
                            idempotency_key=key,
                            request_hash=request_hash,
                            status="placed",
                            total_cents=total_cents,
                            items=[],
                        )
                        await self.repository.add_order(order)
                        for product_id, quantity in items:
                            product = products[product_id]
                            if not await self.repository.decrement_stock(product_id, quantity):
                                raise ConflictError(
                                    f"Insufficient stock for {product.sku}",
                                    error_code="insufficient_stock",
                                )
                            order.items.append(
                                OrderItem(
                                    product_id=product.id,
                                    product_name=product.name,
                                    product_sku=product.sku,
                                    unit_price_cents=product.price,
                                    quantity=quantity,
                                    line_total_cents=product.price * quantity,
                                )
                            )
                        await self.db.flush()
            await self.db.commit()
            return order
        except IntegrityError:
            await self.db.rollback()
            existing = await self.repository.get_by_idempotency_key(user_id, key)
            if existing:
                return self._replay_or_conflict(existing, request_hash)
            raise

    async def get_user_orders(self, user_id: UUID) -> list[Order]:
        return await self.repository.get_user_orders(user_id)