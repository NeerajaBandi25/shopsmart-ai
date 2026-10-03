"""Deterministic promotion eligibility and integer-cent calculation."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy import select

from src.core.exceptions import AppException
from src.models.product import Product
from src.repositories.promotion_repository import PromotionRepository

COUPON_CODE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{0,31}\Z")


@dataclass(frozen=True)
class PromotionEvaluation:
    promotion_id: UUID | str | None
    code: str | None
    eligible: bool
    reason_code: str
    discount_cents: int
    applied_scope: dict[str, str]
    name: str | None = None
    promotion_type: str | None = None
    value: int | None = None


PromotionLine = tuple[object, int]


def _ineligible(promotion, reason_code: str, applied_scope: dict[str, str]) -> PromotionEvaluation:
    return PromotionEvaluation(
        promotion_id=promotion.id,
        code=promotion.code,
        eligible=False,
        reason_code=reason_code,
        discount_cents=0,
        applied_scope=applied_scope,
        name=promotion.name,
        promotion_type=promotion.promotion_type,
        value=promotion.value,
    )


def evaluate_promotion(
    promotion,
    *,
    user_id: UUID,
    lines: Sequence[PromotionLine],
    now: datetime,
) -> PromotionEvaluation:
    """Evaluate one promotion against current product lines and shopper context."""
    applied_scope: dict[str, str] = {"type": promotion.scope_type}
    if promotion.scope_type == "category":
        applied_scope["category"] = promotion.scope_category or ""
    elif promotion.scope_type == "product":
        applied_scope["product_id"] = str(promotion.scope_product_id or "")

    if now.tzinfo is None or now.utcoffset() is None:
        return _ineligible(promotion, "invalid_time_window", applied_scope)
    if (
        promotion.starts_at.tzinfo is None
        or promotion.starts_at.utcoffset() is None
        or promotion.ends_at.tzinfo is None
        or promotion.ends_at.utcoffset() is None
        or promotion.ends_at <= promotion.starts_at
    ):
        return _ineligible(promotion, "invalid_time_window", applied_scope)
    now_utc = now.astimezone(timezone.utc)
    if not promotion.active:
        return _ineligible(promotion, "inactive", applied_scope)
    if now_utc < promotion.starts_at.astimezone(timezone.utc):
        return _ineligible(promotion, "not_started", applied_scope)
    if now_utc >= promotion.ends_at.astimezone(timezone.utc):
        return _ineligible(promotion, "expired", applied_scope)
    if promotion.eligible_user_id is not None and promotion.eligible_user_id != user_id:
        return _ineligible(promotion, "wrong_user", applied_scope)

    if promotion.scope_type not in {"all", "category", "product"}:
        return _ineligible(promotion, "invalid_scope", applied_scope)

    cart_subtotal_cents = 0
    scoped_subtotal_cents = 0
    for product, quantity in lines:
        price_cents = getattr(product, "price", None)
        if not isinstance(price_cents, int) or price_cents < 0 or quantity < 1:
            return _ineligible(promotion, "invalid_value", applied_scope)
        line_total_cents = price_cents * quantity
        cart_subtotal_cents += line_total_cents
        if promotion.scope_type == "all":
            matches_scope = True
        elif promotion.scope_type == "category":
            matches_scope = product.category == promotion.scope_category
        else:
            matches_scope = product.id == promotion.scope_product_id
        if matches_scope:
            scoped_subtotal_cents += line_total_cents

    if scoped_subtotal_cents <= 0:
        return _ineligible(promotion, "scope_mismatch", applied_scope)
    if (
        promotion.min_cart_total_cents is not None
        and cart_subtotal_cents < promotion.min_cart_total_cents
    ):
        return _ineligible(promotion, "cart_below_minimum", applied_scope)

    if promotion.promotion_type == "percentage" and 1 <= promotion.value <= 100:
        discount_cents = (scoped_subtotal_cents * promotion.value + 50) // 100
    elif promotion.promotion_type == "fixed" and promotion.value > 0:
        discount_cents = promotion.value
    else:
        return _ineligible(promotion, "invalid_value", applied_scope)

    discount_cents = min(discount_cents, scoped_subtotal_cents)
    if promotion.max_discount_cents is not None:
        if promotion.max_discount_cents <= 0:
            return _ineligible(promotion, "invalid_value", applied_scope)
        discount_cents = min(discount_cents, promotion.max_discount_cents)

    return PromotionEvaluation(
        promotion_id=promotion.id,
        code=promotion.code,
        eligible=True,
        reason_code="eligible",
        discount_cents=max(0, discount_cents),
        applied_scope=applied_scope,
        name=promotion.name,
        promotion_type=promotion.promotion_type,
        value=promotion.value,
    )


def choose_promotion(
    evaluations: Sequence[PromotionEvaluation],
) -> PromotionEvaluation | None:
    """Choose one best eligible promotion with a stable coupon/id tie-break."""
    eligible = [result for result in evaluations if result.eligible and result.discount_cents > 0]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda result: (
            -result.discount_cents,
            result.code is None,
            str(result.promotion_id),
        ),
    )


def normalize_coupon_code(code: str) -> str:
    """Normalize bounded ASCII coupon input or return a generic validation error."""
    if not isinstance(code, str):
        raise AppException("Coupon code is invalid", 422, "invalid_coupon")
    normalized = code.strip().upper()
    if not COUPON_CODE_PATTERN.fullmatch(normalized):
        raise AppException("Coupon code is invalid", 422, "invalid_coupon")
    return normalized


class PromotionService:
    """Load authoritative candidates and calculate complete cart quotes."""

    def __init__(self, db):
        self.repository = PromotionRepository(db)
        self.db = db

    @staticmethod
    def _evaluation_payload(result: PromotionEvaluation, *, hide_private: bool = False) -> dict:
        return {
            "promotion_id": (
                None if hide_private or result.promotion_id is None else str(result.promotion_id)
            ),
            "code": None if hide_private else result.code,
            "name": None if hide_private else result.name,
            "eligible": result.eligible,
            "reason_code": "coupon_unavailable" if hide_private else result.reason_code,
            "discount_cents": result.discount_cents,
            "applied_scope": {} if hide_private else result.applied_scope,
        }

    def _sqlite_utc(self, promotion) -> None:
        """Restore UTC on SQLite values, whose dialect drops timezone metadata."""
        bind = self.db.get_bind()
        if bind.dialect.name != "sqlite":
            return
        for attribute in ("starts_at", "ends_at"):
            value = getattr(promotion, attribute)
            if value.tzinfo is None:
                setattr(promotion, attribute, value.replace(tzinfo=timezone.utc))

    def evaluate_coupon(
        self,
        promotion,
        *,
        user_id: UUID,
        lines: Sequence[PromotionLine],
        now: datetime,
    ) -> PromotionEvaluation:
        if promotion.eligible_user_id is not None and promotion.eligible_user_id != user_id:
            return PromotionEvaluation(
                promotion_id=None,
                code=None,
                eligible=False,
                reason_code="coupon_unavailable",
                discount_cents=0,
                applied_scope={},
            )
        self._sqlite_utc(promotion)
        result = evaluate_promotion(promotion, user_id=user_id, lines=lines, now=now)
        return result

    async def quote(
        self,
        user_id: UUID,
        lines: Sequence[PromotionLine],
        coupon_code: str | None = None,
        *,
        now: datetime | None = None,
    ) -> dict:
        evaluation_time = now or datetime.now(timezone.utc)
        if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
            raise ValueError("Promotion evaluation requires a timezone-aware clock")

        subtotal = sum(product.price * quantity for product, quantity in lines)
        candidates = await self.repository.list_automatic(user_id, evaluation_time)
        evaluations: list[PromotionEvaluation] = []
        by_id = {}
        for promotion in candidates:
            self._sqlite_utc(promotion)
            result = evaluate_promotion(
                promotion,
                user_id=user_id,
                lines=lines,
                now=evaluation_time,
            )
            evaluations.append(result)
            by_id[str(promotion.id)] = promotion

        coupon_evaluation = None
        if coupon_code is not None:
            try:
                normalized_code = normalize_coupon_code(coupon_code)
            except AppException:
                normalized_code = None
            promotion = (
                await self.repository.get_by_code(normalized_code)
                if normalized_code is not None
                else None
            )
            if promotion is None:
                coupon_result = PromotionEvaluation(
                    promotion_id=None,
                    code=None,
                    eligible=False,
                    reason_code="unknown_or_ineligible",
                    discount_cents=0,
                    applied_scope={},
                )
            else:
                coupon_result = self.evaluate_coupon(
                    promotion,
                    user_id=user_id,
                    lines=lines,
                    now=evaluation_time,
                )
                by_id[str(promotion.id)] = promotion
            coupon_evaluation = self._evaluation_payload(
                coupon_result,
                hide_private=coupon_result.reason_code == "coupon_unavailable",
            )
            evaluations.append(coupon_result)

        selected = choose_promotion(evaluations)
        selected_promotion = by_id.get(str(selected.promotion_id)) if selected else None
        discount = selected.discount_cents if selected else 0
        applied_promotions = []
        if selected is not None and selected_promotion is not None:
            applied_promotions.append(
                {
                    "promotion_id": str(selected_promotion.id),
                    "code": selected_promotion.code,
                    "name": selected_promotion.name,
                    "promotion_type": selected_promotion.promotion_type,
                    "value": selected_promotion.value,
                    "discount_cents": discount,
                    "applied_scope": selected.applied_scope,
                }
            )

        return {
            "subtotal": subtotal,
            "coupon_code": coupon_code,
            "coupon_evaluation": coupon_evaluation,
            "applied_promotions": applied_promotions,
            "discount_total_cents": discount,
            "total_cents": max(0, subtotal - discount),
            "currency": "INR",
            "evaluated_at": evaluation_time.isoformat(),
        }

    async def list_available(
        self,
        user_id: UUID,
        *,
        category: str | None = None,
        product_id: UUID | None = None,
        now: datetime | None = None,
    ) -> list[dict]:
        evaluation_time = now or datetime.now(timezone.utc)
        promotions = await self.repository.list_active(user_id, evaluation_time)
        product_categories = {}
        if product_id is not None:
            product = await self.db.get(Product, product_id)
            if product is None or not product.is_active:
                return []
            product_categories[product.id] = product.category
        elif category is not None:
            scoped_product_ids = {
                promotion.scope_product_id
                for promotion in promotions
                if promotion.scope_type == "product" and promotion.scope_product_id is not None
            }
            if scoped_product_ids:
                result = await self.db.execute(
                    select(Product.id, Product.category).where(Product.id.in_(scoped_product_ids))
                )
                product_categories = dict(result.all())
        available = []
        for promotion in promotions:
            self._sqlite_utc(promotion)
            if product_id is not None:
                if promotion.scope_type == "product" and promotion.scope_product_id != product_id:
                    continue
                if (
                    promotion.scope_type == "category"
                    and promotion.scope_category != product_categories[product_id]
                ):
                    continue
            elif category is not None:
                if promotion.scope_type == "category" and promotion.scope_category != category:
                    continue
                if (
                    promotion.scope_type == "product"
                    and product_categories.get(promotion.scope_product_id) != category
                ):
                    continue
            available.append(
                {
                    "promotion_id": str(promotion.id),
                    "code": promotion.code,
                    "name": promotion.name,
                    "description": promotion.description,
                    "promotion_type": promotion.promotion_type,
                    "value": promotion.value,
                    "scope_type": promotion.scope_type,
                    "scope_category": promotion.scope_category,
                    "scope_product_id": (
                        str(promotion.scope_product_id) if promotion.scope_product_id else None
                    ),
                    "min_cart_total_cents": promotion.min_cart_total_cents,
                    "max_discount_cents": promotion.max_discount_cents,
                    "ends_at": promotion.ends_at.isoformat(),
                }
            )
        return available
