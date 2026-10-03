"""Business rules for the authenticated persistent cart."""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppException, ValidationError
from src.repositories.cart_repository import CartRepository
from src.services.promotion_service import PromotionService, normalize_coupon_code

_promotion_logger = logging.getLogger("shopsmart.promotions")


class CartService:
    """Validate cart mutations and calculate totals from current product data."""

    def __init__(self, db: AsyncSession):
        self.repository = CartRepository(db)
        self.promotions = PromotionService(db)
        self.db = db

    async def get_cart(self, user_id: UUID) -> dict:
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            return self._empty_response()
        return await self._cart_response(cart.id, user_id, cart.coupon_code)

    async def add_item(
        self, user_id: UUID, product_id: UUID, quantity: int, *, commit: bool = True
    ) -> dict:
        cart = await self.repository.get_or_create_cart(user_id)
        product = await self._get_available_product(product_id)
        existing = await self.repository.get_item(cart.id, product_id)
        requested_quantity = quantity + (existing.quantity if existing else 0)
        self._validate_quantity(
            requested_quantity, product.stock_quantity, product.max_purchase_quantity
        )
        await self.repository.set_item_quantity(cart.id, product_id, requested_quantity)
        if commit:
            await self.db.commit()
        return await self._cart_response(cart.id, user_id, cart.coupon_code)

    async def set_item_quantity(self, user_id: UUID, product_id: UUID, quantity: int) -> dict:
        cart = await self.repository.get_or_create_cart(user_id)
        product = await self._get_available_product(product_id)
        self._validate_quantity(quantity, product.stock_quantity, product.max_purchase_quantity)
        await self.repository.set_item_quantity(cart.id, product_id, quantity)
        await self.db.commit()
        return await self._cart_response(cart.id, user_id, cart.coupon_code)

    async def remove_item(self, user_id: UUID, product_id: UUID, *, commit: bool = True) -> dict:
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            return self._empty_response()
        await self.repository.delete_item(cart.id, product_id)
        if commit:
            await self.db.commit()
        return await self._cart_response(cart.id, user_id, cart.coupon_code)

    async def apply_coupon(self, user_id: UUID, code: str, *, commit: bool = True) -> dict:
        started_at = perf_counter()
        try:
            normalized_code = normalize_coupon_code(code)
        except AppException:
            self._log_promotion_operation(
                "coupon_apply",
                success=False,
                reason="unavailable",
                coupon_hash=self._coupon_hash(code),
                status_code=422,
                started_at=started_at,
            )
            raise
        coupon_hash = self._coupon_hash(normalized_code)
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            self._log_promotion_operation(
                "coupon_apply",
                success=False,
                reason="unavailable",
                coupon_hash=coupon_hash,
                status_code=422,
                started_at=started_at,
            )
            raise AppException("Coupon code is invalid or unavailable", 422, "invalid_coupon")
        lines = [
            (product, cart_item.quantity)
            for cart_item, product in await self.repository.list_items(cart.id)
        ]
        promotion = await self.promotions.repository.get_by_code(normalized_code)
        if promotion is None:
            self._log_promotion_operation(
                "coupon_apply",
                success=False,
                reason="unavailable",
                coupon_hash=coupon_hash,
                status_code=422,
                started_at=started_at,
            )
            raise AppException("Coupon code is invalid or unavailable", 422, "invalid_coupon")
        now = datetime.now(timezone.utc)
        result = self.promotions.evaluate_coupon(
            promotion,
            user_id=user_id,
            lines=lines,
            now=now,
        )
        if not result.eligible:
            self._log_promotion_operation(
                "coupon_apply",
                success=False,
                reason="unavailable",
                coupon_hash=coupon_hash,
                status_code=422,
                started_at=started_at,
            )
            raise AppException("Coupon code is invalid or unavailable", 422, "invalid_coupon")
        cart.coupon_code = normalized_code
        if commit:
            await self.db.commit()
        response = await self._cart_response(cart.id, user_id, normalized_code)
        applied = response["applied_promotions"]
        self._log_promotion_operation(
            "coupon_apply",
            success=True,
            coupon_hash=coupon_hash,
            eligible=response["coupon_evaluation"]["eligible"],
            promotion_id=applied[0]["promotion_id"] if applied else None,
            discount_cents=response["discount_total_cents"],
            status_code=200,
            started_at=started_at,
        )
        return response

    async def remove_coupon(self, user_id: UUID, *, commit: bool = True) -> dict:
        started_at = perf_counter()
        cart = await self.repository.get_cart(user_id)
        if cart is None:
            self._log_promotion_operation(
                "coupon_remove", success=True, status_code=200, started_at=started_at
            )
            return self._empty_response()
        coupon_hash = self._coupon_hash(cart.coupon_code) if cart.coupon_code else None
        cart.coupon_code = None
        if commit:
            await self.db.commit()
        response = await self._cart_response(cart.id, user_id, None)
        applied = response["applied_promotions"]
        self._log_promotion_operation(
            "coupon_remove",
            success=True,
            coupon_hash=coupon_hash,
            promotion_id=applied[0]["promotion_id"] if applied else None,
            discount_cents=response["discount_total_cents"],
            status_code=200,
            started_at=started_at,
        )
        return response

    async def check_coupon(self, user_id: UUID, code: str) -> dict:
        started_at = perf_counter()
        try:
            normalized_code = normalize_coupon_code(code)
        except AppException:
            self._log_promotion_operation(
                "coupon_check",
                success=False,
                reason="unavailable",
                coupon_hash=self._coupon_hash(code),
                status_code=422,
                started_at=started_at,
            )
            raise
        coupon_hash = self._coupon_hash(normalized_code)
        cart = await self.repository.get_cart(user_id)
        lines = (
            [
                (product, cart_item.quantity)
                for cart_item, product in await self.repository.list_items(cart.id)
            ]
            if cart is not None
            else []
        )
        quote = await self.promotions.quote(user_id, lines, normalized_code)
        evaluation = quote["coupon_evaluation"] or {}
        self._log_promotion_operation(
            "coupon_check",
            success=True,
            reason=evaluation.get("reason_code", "unavailable"),
            coupon_hash=coupon_hash,
            eligible=evaluation.get("eligible", False),
            promotion_id=(
                quote["applied_promotions"][0]["promotion_id"]
                if quote["applied_promotions"]
                else None
            ),
            discount_cents=quote["discount_total_cents"],
            status_code=200,
            started_at=started_at,
        )
        return quote

    async def get_available_promotions(
        self, user_id: UUID, *, category: str | None = None, product_id: UUID | None = None
    ) -> list[dict]:
        started_at = perf_counter()
        promotions = await self.promotions.list_available(
            user_id,
            category=category,
            product_id=product_id,
        )
        self._log_promotion_operation(
            "offer_list",
            success=True,
            result_count=len(promotions),
            status_code=200,
            started_at=started_at,
        )
        return promotions

    @staticmethod
    def _log_promotion_operation(
        operation: str,
        *,
        success: bool,
        reason: str | None = None,
        result_count: int | None = None,
        promotion_id: str | None = None,
        coupon_hash: str | None = None,
        eligible: bool | None = None,
        discount_cents: int | None = None,
        status_code: int | None = None,
        started_at: float,
    ) -> None:
        context = {
            "event": "promotion_operation",
            "operation": operation,
            "success": success,
        }
        if reason is not None:
            context["reason"] = reason[:64]
        if result_count is not None:
            context["result_count"] = result_count
        if promotion_id is not None:
            context["promotion_id"] = promotion_id[:64]
        if coupon_hash is not None:
            context["coupon_hash"] = coupon_hash
        if eligible is not None:
            context["eligible"] = eligible
        if discount_cents is not None:
            context["discount_cents"] = max(0, discount_cents)
        if status_code is not None:
            context["status_code"] = status_code
        context["duration_ms"] = round((perf_counter() - started_at) * 1000, 3)
        _promotion_logger.info("promotion_operation", extra=context)

    @staticmethod
    def _coupon_hash(code: object) -> str | None:
        if not isinstance(code, str):
            return None
        return hmac.new(
            settings.secret_key.encode("utf-8"),
            code[:64].encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _empty_response() -> dict:
        return {
            "items": [],
            "subtotal": 0,
            "currency": "INR",
            "coupon_code": None,
            "coupon_evaluation": None,
            "applied_promotions": [],
            "discount_total_cents": 0,
            "total_cents": 0,
        }

    async def _get_available_product(self, product_id: UUID):
        product = await self.repository.get_product(product_id, lock=True)
        if product is None or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    @staticmethod
    def _validate_quantity(quantity: int, stock_quantity: int, max_purchase_quantity: int) -> None:
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1", "invalid_quantity")
        if quantity > stock_quantity:
            raise ValidationError(
                "Requested quantity exceeds available stock", "insufficient_stock"
            )
        if quantity > max_purchase_quantity:
            raise ValidationError("Requested quantity exceeds the purchase limit", "quantity_limit")

    async def _cart_response(self, cart_id: UUID, user_id: UUID, coupon_code: str | None) -> dict:
        items = []
        lines = await self.repository.list_items(cart_id)
        for cart_item, product in lines:
            line_total = product.price * cart_item.quantity
            items.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                    "image_url": product.image_url,
                    "image_alt": product.image_alt,
                    "unit_price": product.price,
                    "quantity": cart_item.quantity,
                    "line_total": line_total,
                    "stock_quantity": product.stock_quantity,
                    "max_purchase_quantity": product.max_purchase_quantity,
                }
            )
        quote = await self.promotions.quote(
            user_id,
            [(product, cart_item.quantity) for cart_item, product in lines],
            coupon_code,
        )
        return {"items": items, **quote}
