# Research: Promotions and Discount Engine

**Feature**: [spec.md](spec.md)
**Date**: 2026-10-03

## Repository Findings

- `Product.price` is an integer in USD cents: catalog filters, assistant result fields, frontend formatting, existing tests, and order item snapshots use cents.
- `CartService` calculates an integer-cent subtotal from the current product rows. `OrderService` independently calculates checkout totals from locked current products and already provides idempotency and stock rollback.
- `Cart` is unique per user and currently stores only lines. Cart APIs derive ownership from the authenticated user and require CSRF for mutations.
- `Order` stores `total_cents`; `OrderItem` stores immutable product/price/line snapshots. Checkout accepts only product IDs and quantities and rejects extra fields.
- The assistant router already recognizes `PROMOTIONS`, but the handler returns a fixed no-offer answer. There are no promotion records, services, repositories, or coupon UI. RAG is already reserved for stable policy information.
- Current canonical categories are defined by `PRODUCT_CATEGORIES`. Migration 012 is the current head; Alembic imports models explicitly.
- Production-like seed data uses stable UUIDs, reserved SKUs, explicit local/test opt-in, loopback-only database validation, and ownership-checked reset. The evaluator uses a deterministic provider and a versioned JSON dataset.

## Decisions

### Authoritative records and scope

Use one persisted promotion record as the only discount definition. Do not add promotion facts to the knowledge corpus or ask a model/provider to calculate eligibility. Promotion writes remain restricted to trusted backend/seed operations; there is no public CRUD route because the existing user model has no staff-role boundary.

A promotion has one of three explicit scopes: all products, one canonical category, or one product. It may optionally target one user. There is no membership-tier or payment-method model in this codebase, so neither is added.

### Eligibility and time

Use an injectable timezone-aware UTC evaluation instant and the half-open interval `starts_at <= now < ends_at`. `active` is independently required. Evaluate category/product scope using loaded `Product.id` and `Product.category`; do not use product descriptions or semantic retrieval. The cart threshold uses the full pre-discount cart subtotal, while the discount base includes only matching scope lines.

Normalize coupon input with trim plus uppercase and restrict its format/length. Resolve coupons case-insensitively. Distinguish stable internal reason codes for inactive, future, expired, wrong shopper, threshold, scope, invalid value, and eligible outcomes. Public invalid-code errors do not disclose another shopper's promotion.

### Money and selection

Keep all calculations as integer USD cents. Percentage promotions use whole-number percent values from 1 through 100 and half-up rounding: `(base_cents * percent + 50) // 100`. Fixed amounts are integer cents. Both are capped at the scoped subtotal and, when configured, `max_discount_cents`.

Do not support stacking in v1. Consider all eligible automatic promotions and the currently selected coupon as independent candidates; select the greatest discount. On equal discounts, prefer the entered coupon and then the lexicographically smallest promotion ID. This is deterministic, favors the shopper, and keeps overlapping offers from compounding.

### Cart state

Persist only the normalized coupon code on the owner's existing cart. Never persist a quoted discount amount or final total. Every cart read and mutation recomputes current prices, applicable active promotions, coupon eligibility, selected result, and final total. An invalid apply request does not overwrite the prior code. If a stored coupon later becomes ineligible, report its reason and allow another eligible automatic promotion to win; the shopper can remove the stale code.

Keep the existing integer-cent `subtotal` response field for compatibility and add explicit discount/final-total fields plus structured promotion details.

### Checkout and order history

Retain the established checkout transaction: validate item lines, lock products, check stock, then evaluate promotions and write order/items before committing. The request may include a bounded coupon code but never prices or totals. Include normalized code in the idempotency request hash. Persist `subtotal_cents`, `discount_total_cents`, `total_cents`, and an immutable promotion snapshot on `Order`; keep `OrderItem` line values as pre-discount catalog snapshots. Existing orders are backfilled with `subtotal_cents = total_cents`, zero discount, and an empty snapshot.

### Assistant and interface

Reuse the existing authenticated assistant route and deterministic router. Separate explicit `COUPON_APPLY` and `COUPON_REMOVE` actions from `PROMOTIONS` browsing/checking. A question such as "Can I use SAVE10?" is read-only; "Apply SAVE10" may mutate the current user's cart. The assistant uses bounded service methods and the current user injected by the backend. It receives promotion/cart results before writing any discount explanation. It does not query RAG for promotions and does not need an LLM for simple answers.

### Seed, evaluator, and privacy

Extend the existing versioned local manifest with deterministic promotion cases while keeping its current product/user namespace and IDs. Add promotion ownership checks and remove only known synthetic promotion records during reset. Keep seed/reset/evaluation under the current local/test/loopback safety checks. Use fixed evaluation time for windows and use synthetic data only.

Emit structured promotion logs using request ID, operation, promotion ID or one-way coupon hash, eligibility, reason code, discount cents, safe cart ID, duration, and status. Never log raw prompts, auth material, payment data, secrets, or raw coupon input.

## Alternatives Considered

- **RAG or model-authored discounts**: rejected because policy knowledge is not transactional authority and free text cannot enforce expiry, scope, or cents.
- **Persisting discount totals on carts**: rejected because product, cart, user, and promotion state can change; a code is only a re-evaluation request.
- **Stacking multiple promotions**: rejected for v1 because it expands ordering and cap semantics without an existing product requirement; single-winner rules are explicit and reproducible.
- **Public promotion administration endpoints**: rejected because no staff authorization model exists. Adding unauthenticated or shopper-accessible writes would weaken security.
- **Client-selected final totals**: rejected; only product/quantity and optional code cross checkout, and the backend recalculates inside the order transaction.
- **New money or promotion dependency**: rejected because integer arithmetic and SQLAlchemy/PostgreSQL already cover the requirements.
