# Data Model: Promotions and Discount Engine

## Promotion

Authoritative backend-owned offer definition. Inherited `id`, `created_at`, and `updated_at` use the existing base-model conventions.

| Field | Type / nullability | Rules |
|---|---|---|
| `code` | string, nullable | Optional; 1-32 uppercase ASCII letters/digits/underscore/hyphen after normalization; case-insensitive unique when present. `NULL` means automatic. |
| `name` | string, required | 1-120 characters. |
| `description` | string, nullable | At most 500 characters; display text only, never executable eligibility logic. |
| `promotion_type` | string, required | `percentage` or `fixed`; database check constraint. |
| `value` | integer, required | Percentage: whole percent 1-100. Fixed: positive USD cents. No floating point. |
| `starts_at` | timezone-aware timestamp, required | UTC instant, inclusive lower bound. |
| `ends_at` | timezone-aware timestamp, required | UTC instant, exclusive upper bound; must be later than `starts_at`. |
| `active` | boolean, required | Must be true in addition to the time-window check. |
| `scope_type` | string, required | `all`, `category`, or `product`. |
| `scope_category` | string, nullable | Required only for category scope and constrained to current canonical product categories. |
| `scope_product_id` | UUID FK, nullable | Required only for product scope; deletion restricted. |
| `min_cart_total_cents` | integer, nullable | Must be nonnegative; compared to the whole cart pre-discount subtotal. |
| `max_discount_cents` | integer, nullable | Must be positive when present; caps calculated discount. |
| `eligible_user_id` | UUID FK, nullable | Optional shopper restriction; cascade on user deletion; compare only to authenticated owner. |

Constraints/indexes:

- Case-insensitive unique partial index over non-null `code`.
- Check that type/value ranges are consistent.
- Check that scope target fields match scope type: all has neither target; category has category only; product has product only.
- Check `ends_at > starts_at`, threshold >= 0, maximum discount > 0.
- Index active/start/end, scope category, and eligible user as query patterns justify.
- No redemption counter, stacking flag, membership tier, or payment-method relation in v1.

## Cart Extension

Add `coupon_code: string | null` to the existing one-cart-per-user row. It stores only a normalized code request. It stores no eligibility decision, discount, subtotal, or payable total. Cart lines continue to reference current products and are owner-scoped through the existing cart repository.

## Promotion Evaluation Result

An immutable service result, not a persisted entity:

| Field | Type | Meaning |
|---|---|---|
| `promotion_id` | UUID or null | Present only when a known promotion may safely be identified. |
| `eligible` | boolean | Whether current user, time, code, scope, and cart conditions all pass. |
| `reason_code` | bounded string enum | Stable machine-readable eligibility result. |
| `discount_cents` | nonnegative integer | Calculated amount, capped to applicable subtotal and maximum. Zero when ineligible. |
| `applied_scope` | typed object | Scope type and canonical category/product identity that formed the eligible base. |

The cart pricing result includes ordered line snapshots, whole-cart `subtotal_cents`, current `coupon_code`, coupon evaluation if supplied, at most one selected `applied_promotions` result, `discount_total_cents`, `total_cents`, and currency. For compatibility, `subtotal` remains equal to integer-cent `subtotal_cents`.

## Order Pricing Snapshot

Extend `Order` with:

- `subtotal_cents` (nonnegative integer)
- `discount_total_cents` (integer from zero through subtotal)
- `promotion_snapshot` (JSON array, non-null; default empty)

Keep `total_cents` as the authoritative payable amount and enforce `total_cents = subtotal_cents - discount_total_cents`.

Each applied snapshot object captures promotion ID, code when relevant, name, type/value, scope identity, selected discount cents, and evaluation timestamp. Snapshot fields are copied at placement and never joined back to mutable current promotion state when rendering historical orders. Existing rows migrate to their original total as subtotal with no applied promotion.

Existing `OrderItem.unit_price_cents` and `line_total_cents` remain pre-discount product snapshots; the order-level snapshot records the promotion allocation/discount. There is no per-line discount allocation in v1.

## Relationships and Ownership

- Promotion -> optional `Product` target, delete restricted.
- Promotion -> optional eligible `User`, delete cascades the targeted offer.
- Cart -> one `User`, already unique and owner-scoped; coupon state follows that cart.
- Order -> one `User`, existing idempotent ownership boundary; pricing snapshot belongs to that order.
- No client-supplied promotion ID is accepted for applying a code. Unknown IDs/codes never bypass scope evaluation.
