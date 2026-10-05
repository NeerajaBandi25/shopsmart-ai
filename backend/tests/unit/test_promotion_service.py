"""Deterministic promotion eligibility and integer-cent calculation tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.services.promotion_service import PromotionService, choose_promotion, evaluate_promotion

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def _product(*, price: int = 10005, category: str = "laptops"):
    return SimpleNamespace(id=uuid4(), price=price, category=category)


def _promotion(**overrides):
    values = {
        "id": uuid4(),
        "code": None,
        "name": "Test offer",
        "promotion_type": "percentage",
        "value": 10,
        "starts_at": NOW - timedelta(days=1),
        "ends_at": NOW + timedelta(days=1),
        "active": True,
        "scope_type": "all",
        "scope_category": None,
        "scope_product_id": None,
        "min_cart_total_cents": None,
        "max_discount_cents": None,
        "eligible_user_id": None,
    }
    return SimpleNamespace(**(values | overrides))


def _evaluate(promotion, user_id, lines, now=NOW):
    return evaluate_promotion(
        promotion,
        user_id=user_id,
        lines=lines,
        now=now,
    )


def test_percentage_uses_integer_half_up_rounding():
    user_id = uuid4()
    product = _product(price=10005)

    result = _evaluate(_promotion(), user_id, [(product, 1)])

    assert result.eligible is True
    assert result.reason_code == "eligible"
    assert result.discount_cents == 1001
    assert result.applied_scope == {"type": "all"}


def test_percentage_respects_maximum_and_scoped_subtotal():
    user_id = uuid4()
    laptop = _product(price=10000, category="laptops")
    phone = _product(price=8000, category="phones")
    promotion = _promotion(
        value=50,
        scope_type="category",
        scope_category="laptops",
        max_discount_cents=1200,
    )

    result = _evaluate(promotion, user_id, [(laptop, 1), (phone, 1)])

    assert result.eligible is True
    assert result.discount_cents == 1200
    assert result.applied_scope == {"type": "category", "category": "laptops"}


def test_fixed_discount_is_capped_at_matching_product_subtotal():
    user_id = uuid4()
    product = _product(price=250)

    result = _evaluate(
        _promotion(promotion_type="fixed", value=900, max_discount_cents=None),
        user_id,
        [(product, 1)],
    )

    assert result.eligible is True
    assert result.discount_cents == 250


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"active": False}, "inactive"),
        ({"starts_at": NOW + timedelta(seconds=1)}, "not_started"),
        ({"ends_at": NOW}, "expired"),
        ({"eligible_user_id": uuid4()}, "wrong_user"),
        ({"scope_type": "category", "scope_category": "phones"}, "scope_mismatch"),
        ({"min_cart_total_cents": 10006}, "cart_below_minimum"),
    ],
)
def test_ineligible_promotions_return_stable_reasons(changes, reason):
    user_id = uuid4()
    product = _product(price=10005, category="laptops")

    result = _evaluate(_promotion(**changes), user_id, [(product, 1)])

    assert result.eligible is False
    assert result.reason_code == reason
    assert result.discount_cents == 0


def test_minimum_uses_whole_cart_but_discount_uses_matching_scope():
    user_id = uuid4()
    laptop = _product(price=500, category="laptops")
    phone = _product(price=500, category="phones")
    promotion = _promotion(
        promotion_type="fixed",
        value=400,
        scope_type="category",
        scope_category="laptops",
        min_cart_total_cents=1000,
    )

    result = _evaluate(promotion, user_id, [(laptop, 1), (phone, 1)])

    assert result.eligible is True
    assert result.discount_cents == 400


def test_naive_evaluation_time_fails_closed():
    user_id = uuid4()
    product = _product()

    result = _evaluate(_promotion(), user_id, [(product, 1)], now=NOW.replace(tzinfo=None))

    assert result.eligible is False
    assert result.reason_code == "invalid_time_window"
    assert result.discount_cents == 0


@pytest.mark.parametrize(
    "window_changes",
    [
        {"starts_at": NOW + timedelta(days=1)},
        {"ends_at": NOW - timedelta(days=1)},
    ],
    ids=["future-private-coupon", "expired-private-coupon"],
)
def test_private_coupon_hides_window_status_from_non_owner(window_changes):
    owner_id = uuid4()
    other_user_id = uuid4()
    promotion = _promotion(
        code="PRIVATE10",
        eligible_user_id=owner_id,
        **window_changes,
    )
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    )

    result = PromotionService(db).evaluate_coupon(
        promotion,
        user_id=other_user_id,
        lines=[(_product(), 1)],
        now=NOW,
    )

    assert result.eligible is False
    assert result.reason_code == "coupon_unavailable"
    assert result.promotion_id is None
    assert result.code is None
    assert result.name is None
    assert result.discount_cents == 0


def test_invalid_values_never_produce_negative_or_oversized_discounts():
    user_id = uuid4()
    product = _product(price=100)

    negative = _evaluate(_promotion(value=-10), user_id, [(product, 1)])
    oversized_percentage = _evaluate(_promotion(value=101), user_id, [(product, 1)])

    assert negative.reason_code == "invalid_value"
    assert oversized_percentage.reason_code == "invalid_value"
    assert negative.discount_cents == oversized_percentage.discount_cents == 0


def test_selection_is_single_winner_and_ties_are_deterministic():
    user_id = uuid4()
    product = _product(price=10000)
    smallest_id = "00000000-0000-0000-0000-000000000001"
    larger_id = "00000000-0000-0000-0000-000000000002"
    auto = _evaluate(
        _promotion(id=larger_id, value=10),
        user_id,
        [(product, 1)],
    )
    coupon = _evaluate(
        _promotion(id=smallest_id, code="SAVE10", value=10),
        user_id,
        [(product, 1)],
    )

    selected = choose_promotion([auto, coupon])

    assert selected.promotion_id == coupon.promotion_id
    assert choose_promotion([coupon, auto]).promotion_id == selected.promotion_id


def test_highest_discount_wins_without_stacking():
    user_id = uuid4()
    product = _product(price=10000)
    smaller = _evaluate(_promotion(value=10), user_id, [(product, 1)])
    larger = _evaluate(
        _promotion(id=uuid4(), promotion_type="fixed", value=1500),
        user_id,
        [(product, 1)],
    )

    selected = choose_promotion([smaller, larger])

    assert selected.promotion_id == larger.promotion_id
    assert selected.discount_cents == 1500
