# Promotions flow

**What:** Promotions can be automatic or coupon-based, scoped to user/category/product with eligibility rules.

**Why:** Eligibility must be checked against the shopper and current cart on every quote. Private coupons must not become an account enumeration channel.

**How / request flow:** Coupon input → bounded ASCII normalization → promotion repository → ownership/privacy check → current-line eligibility → best eligible discount → quote. Checkout repeats the quote.

**Key files:**

- `backend/src/services/promotion_service.py`
- `backend/src/repositories/promotion_repository.py`
- `backend/src/services/cart_service.py`
- `backend/src/models/promotion.py`
- `backend/tests/integration/test_promotions_api.py`

**Interview talking points:** The engine chooses one best eligible promotion; it does not stack every offer. Equal discounts use a stable coupon/ID tie-break. Logs use a keyed hash rather than the coupon text.
