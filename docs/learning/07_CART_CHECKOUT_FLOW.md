# Cart and checkout flow

**What:** CartService validates current stock and purchase limits, then quotes promotions. OrderService recalculates prices, locks products and saves immutable order lines.

**Why:** A browser cart is a proposal. Its prices and an earlier coupon result can be stale when checkout runs.

**How / request flow:** Add/update → user-scoped cart → current product → quote. Checkout → user-scoped idempotency lookup → locked products → new quote → conditional stock decrement → order snapshots → commit → cache invalidation.

**Key files:**

- `backend/src/services/cart_service.py`
- `backend/src/services/order_service.py`
- `backend/src/repositories/order_repository.py`
- `backend/src/models/order.py`
- `frontend/src/components/CheckoutFlow.tsx`

**Interview talking points:** Retries with the same key and same payload return the prior order. Reusing that key with a different payload returns a conflict. No real payment processor is part of this portfolio checkout.
