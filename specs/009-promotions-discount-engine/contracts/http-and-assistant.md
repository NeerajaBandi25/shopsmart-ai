# HTTP and Assistant Contracts

These contracts extend existing authenticated cart, order, assistant, and same-origin BFF boundaries. Paths are versioned at the FastAPI layer; browser requests use the existing Next.js BFF.

## Cart pricing response

Existing fields remain compatible. All monetary values are integer USD cents.

```json
{
  "items": [],
  "subtotal": 1299,
  "currency": "USD",
  "coupon_code": "SAVE10",
  "coupon_evaluation": {
    "promotion_id": "00000000-0000-0000-0000-000000000000",
    "eligible": true,
    "reason_code": "eligible",
    "discount_cents": 130,
    "applied_scope": {"type": "all"}
  },
  "applied_promotions": [],
  "discount_total_cents": 130,
  "total_cents": 1169
}
```

An ineligible or absent coupon has zero coupon discount. `applied_promotions` contains zero or one selected promotion. `total_cents` is always `max(0, subtotal - discount_total_cents)`.

## Apply coupon

- Backend: `POST /api/v1/cart/coupon`
- BFF: `POST /api/cart/coupon`
- Authentication: current session required; user ID comes from auth dependency.
- Mutation: CSRF token required.
- Request: `{"code":"SAVE10"}`; extra fields forbidden. Trim/uppercase then validate 1-32 characters matching `[A-Z0-9][A-Z0-9_-]{0,31}`.
- Success: full freshly priced cart response.
- Failure: generic 422 safe error; invalid attempt does not replace an existing stored coupon.

## Remove coupon

- Backend: `DELETE /api/v1/cart/coupon`
- BFF: `DELETE /api/cart/coupon`
- Authentication and CSRF: same as apply.
- Request body: none.
- Success: full cart response with code cleared and automatic promotions recalculated.

## Checkout

- Existing: `POST /api/v1/orders/checkout` through `POST /api/orders/checkout`.
- Request continues to accept only `items: [{product_id, quantity}]` plus optional `coupon_code`; no subtotal, unit price, discount, promotion ID, or total fields are accepted.
- The frontend sends only item IDs/quantities and the coupon code from the latest server cart response. These remain untrusted requests, not final pricing.
- Backend re-locks/reloads current products, recalculates all promotion results in the checkout transaction, then writes order item and order pricing snapshots.
- Idempotency request hash covers canonical item IDs/quantities and normalized coupon code.
- Order response includes `subtotal_cents`, `discount_total_cents`, `total_cents`, `promotion_snapshot`, and existing immutable item snapshots.

## Assistant service tools

All operations receive the authenticated `user_id` from the backend; no tool argument may supply an alternate owner or arbitrary promotion ID.

- `get_available_promotions(context?)`: active-window offers for the current user; optional canonical category or an authorized product reference. No RAG.
- `get_product_promotions(product_id)`: product/category/all-scope current offers for a product resolved through catalog service or owned conversation context.
- `evaluate_promotion(code, cart_context)`: read-only eligibility/result; code and cart context validated by service.
- `apply_coupon(code)`: only for explicit apply intent; delegates to current user's cart service and returns the new quote.
- `remove_coupon()`: only for explicit remove intent; delegates to current user's cart service.
- `price_cart()`: returns current authoritative cart pricing.

Router behaviors:

- `PROMOTIONS` handles available-offer and read-only coupon questions, including "Can I use SAVE10?".
- `COUPON_APPLY` handles explicit apply commands only.
- `COUPON_REMOVE` handles explicit removal only.
- Tool arguments are bounded, typed, and validated. Model output cannot select an operation, provide owner IDs, run SQL, or override returned amounts.
- A deterministic response may be returned without a model call. Any optional wording model receives authoritative results and cannot modify the result payload.
