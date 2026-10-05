"""Transactional checkout and shopper-scoped order history."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, ConflictError
from src.core.observability import commerce_audit_event
from src.core.payment_limits import (
    HOSTED_CHECKOUT_MAX_AMOUNT_CENTS,
    HOSTED_CHECKOUT_MIN_AMOUNT_CENTS,
)
from src.models.order import Order, OrderItem
from src.models.user import User
from src.repositories.order_repository import OrderRepository
from src.services.product_catalog_cache import invalidate_product_catalog_cache
from src.services.promotion_service import PromotionService, normalize_coupon_code

MAX_ACTIVE_PENDING_PAYMENT_ORDERS = 3


class OrderService:
    """Apply checkout rules and own the durable transaction boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = OrderRepository(db)

    @staticmethod
    def _request_hash(
        items: list[tuple[UUID, int]],
        coupon_code: str | None = None,
        delivery_address: dict[str, str] | None = None,
    ) -> str:
        canonical = sorted((str(product_id), quantity) for product_id, quantity in items)
        payload = {
            "items": canonical,
            "coupon_code": coupon_code,
            "delivery_address": delivery_address,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
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
        self,
        user_id: UUID,
        key: str,
        items: list[tuple[UUID, int]],
        coupon_code: str | None = None,
        delivery_address: dict[str, str] | None = None,
        initial_status: str = "placed",
        request_id: str | None = None,
    ) -> Order:
        if initial_status not in {"placed", "pending_payment"}:
            raise ValueError("initial_status must be a supported checkout order state")
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

        normalized_coupon = normalize_coupon_code(coupon_code) if coupon_code is not None else None
        request_hash = self._request_hash(items, normalized_coupon, delivery_address)
        products_changed = False
        created_order = False
        try:
            async with self.db.begin_nested():
                existing = await self.repository.get_by_idempotency_key(user_id, key)
                if existing:
                    order = self._replay_or_conflict(existing, request_hash)
                else:
                    if initial_status == "pending_payment":
                        # Serialize this shopper's new payment orders so concurrent distinct
                        # idempotency keys cannot exceed the active reservation cap.
                        locked_user = await self.db.scalar(
                            select(User.id).where(User.id == user_id).with_for_update()
                        )
                        if locked_user is None:
                            raise AppException(
                                "Shopper account was not found", 404, "user_not_found"
                            )
                    # A competing request may have committed while this request waited on row locks.
                    existing = await self.repository.get_by_idempotency_key(user_id, key)
                    if existing:
                        order = self._replay_or_conflict(existing, request_hash)
                    else:
                        if initial_status == "pending_payment":
                            active_count = await self.db.scalar(
                                select(func.count())
                                .select_from(Order)
                                .where(
                                    Order.user_id == user_id,
                                    Order.status == "pending_payment",
                                )
                            )
                            if (active_count or 0) >= MAX_ACTIVE_PENDING_PAYMENT_ORDERS:
                                raise ConflictError(
                                    "You have checkout orders awaiting payment. Continue one or wait for it to expire before starting another.",
                                    error_code="pending_payment_limit",
                                )
                        products = await self.repository.lock_products(product_ids)
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

                        quote = await PromotionService(self.db).quote(
                            user_id,
                            [(products[product_id], quantity) for product_id, quantity in items],
                            normalized_coupon,
                        )
                        if initial_status == "pending_payment" and not (
                            HOSTED_CHECKOUT_MIN_AMOUNT_CENTS
                            <= quote["total_cents"]
                            <= HOSTED_CHECKOUT_MAX_AMOUNT_CENTS
                        ):
                            raise AppException(
                                "This order total is not supported by hosted checkout",
                                422,
                                "hosted_checkout_amount_unsupported",
                            )
                        promotion_snapshot = [
                            {**promotion, "evaluated_at": quote["evaluated_at"]}
                            for promotion in quote["applied_promotions"]
                        ]
                        order = Order(
                            user_id=user_id,
                            idempotency_key=key,
                            request_hash=request_hash,
                            status=initial_status,
                            subtotal_cents=quote["subtotal"],
                            discount_total_cents=quote["discount_total_cents"],
                            total_cents=quote["total_cents"],
                            promotion_snapshot=promotion_snapshot,
                            delivery_address=delivery_address,
                            items=[],
                        )
                        created_order = True
                        await self.repository.add_order(order)
                        for product_id, quantity in items:
                            product = products[product_id]
                            if not await self.repository.decrement_stock(product_id, quantity):
                                raise ConflictError(
                                    f"Insufficient stock for {product.sku}",
                                    error_code="insufficient_stock",
                                )
                            products_changed = True
                            order.items.append(
                                OrderItem(
                                    product_id=product.id,
                                    product_name=product.name,
                                    product_sku=product.sku,
                                    product_image_url=product.image_url,
                                    product_image_alt=product.image_alt,
                                    unit_price_cents=product.price,
                                    quantity=quantity,
                                    line_total_cents=product.price * quantity,
                                )
                            )
                        await self.db.flush()
            await self.db.commit()
            if products_changed:
                await invalidate_product_catalog_cache()
            if created_order:
                commerce_audit_event(
                    "ORDER_CREATED",
                    request_id=request_id,
                    order_id=str(order.id),
                    amount_cents=order.total_cents,
                    currency="INR",
                    status=order.status,
                )
            return order
        except IntegrityError:
            await self.db.rollback()
            existing = await self.repository.get_by_idempotency_key(user_id, key)
            if existing:
                return self._replay_or_conflict(existing, request_hash)
            raise

    async def get_user_orders(self, user_id: UUID) -> list[Order]:
        return await self.repository.get_user_orders(user_id)

    async def get_user_order(self, user_id: UUID, order_id: UUID) -> Order | None:
        return await self.repository.get_user_order(user_id, order_id)
