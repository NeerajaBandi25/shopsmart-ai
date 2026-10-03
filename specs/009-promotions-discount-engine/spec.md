# Feature Specification: ShopSmart Promotions and Discount Engine

**Feature Branch**: `feature/promotions-discount-engine`
**Created**: 2026-10-03
**Status**: Draft
**Input**: User request to add an authoritative promotion engine integrated with cart, checkout, assistant, synthetic data, evaluations, and browser validation.

## Product Role and Authority

Promotions are authoritative commerce data. Only persisted promotion records evaluated against the current time, authenticated shopper, current product/category scope, and current cart/order lines may produce a discount. RAG, free-text model output, client totals, and provider guesses are never promotion sources. The assistant may describe a promotion only after receiving the corresponding authoritative service result; it must not create or alter that result.

Version 1 supports public promotions and an optional single-shopper eligibility restriction. Membership tiers, payment-method targeting, redemption limits, campaign management UI, and stacking are out of scope. Trusted backend operators own promotion data; there is no public promotion-write API. All promotions are mutually exclusive in v1, and the deterministic winner is the eligible candidate with the greatest discount; ties prefer the explicitly entered coupon, then the lexicographically smallest promotion ID. A stored coupon is one candidate, not an instruction to bypass eligibility. If it becomes ineligible after a cart change, its reason is returned and another eligible automatic promotion may win.

## User Scenarios and Testing

### User Story 1 - See an accurate cart price with offers applied (Priority: P1)

An authenticated shopper sees current item prices, subtotal, applicable promotions, total discount, and final payable total in the cart. Changing cart items or quantities recalculates the result from current server data.

**Why this priority**: Pricing correctness is the engine's core customer and financial contract.

**Independent Test**: Create products and promotions in a test database, read and mutate an authenticated cart, and compare every returned amount to an independently calculated integer-cent expectation.

**Acceptance Scenarios**:

1. **Given** an active applicable automatic promotion, **When** the shopper reads the cart, **Then** the cart contains the authoritative subtotal, selected promotion, discount, and nonnegative final total.
2. **Given** a product-scoped or category-scoped promotion, **When** cart lines do not match that scope, **Then** those lines contribute no discount base.
3. **Given** a cart change makes a threshold promotion eligible or ineligible, **When** the cart is recalculated, **Then** the returned promotion result and total reflect the new cart immediately.
4. **Given** a second shopper, **When** they read or mutate their cart, **Then** no coupon state, lines, or totals from the first shopper are visible or changed.

### User Story 2 - Apply, validate, and remove a coupon (Priority: P1)

An authenticated shopper can submit one coupon code to their own cart, receive a safe eligibility result, and remove the code. The code is stored as a request for re-evaluation, never as trusted discount state.

**Why this priority**: Coupon interaction is the primary explicit promotion workflow and must remain safe across later cart changes.

**Independent Test**: Apply known-valid, unknown, expired, future, wrong-scope, wrong-user, and below-threshold codes through the authenticated cart API; verify both response and persisted cart state.

**Acceptance Scenarios**:

1. **Given** an active eligible coupon, **When** the shopper applies its code, **Then** the next server-priced cart includes its deterministic result if it wins the no-stacking selection rule.
2. **Given** an unknown, malformed, expired, future, out-of-scope, or wrong-shopper code, **When** the shopper applies it, **Then** the response fails safely, no discount is applied, and no previous valid cart state is silently overwritten.
3. **Given** a selected coupon and a later cart mutation, **When** cart pricing is recalculated, **Then** eligibility is re-evaluated against the updated cart rather than cached discount amounts.
4. **Given** a selected coupon, **When** the shopper removes it, **Then** the coupon code is cleared and eligible automatic promotions are recalculated.

### User Story 3 - Place an order at current authoritative pricing (Priority: P1)

At checkout, the backend re-loads and locks current products, validates inventory, re-evaluates the optional coupon and all applicable promotions, and stores an immutable pricing/promotion snapshot with the order. The client never supplies an amount used as the payable total.

**Why this priority**: A cart quote can become stale between display and checkout; the order transaction must remain authoritative and idempotent.

**Independent Test**: Quote a discounted cart, change promotion timing or cart inputs before checkout, then verify checkout recalculates from current state and replays the same idempotent order only for the same normalized items and coupon.

**Acceptance Scenarios**:

1. **Given** a valid cart quote, **When** checkout is submitted with product IDs, quantities, and an optional code, **Then** the order subtotal, discount, final total, and snapshot are calculated from locked current records.
2. **Given** a coupon expires or no longer meets scope/threshold before checkout, **When** the order is placed, **Then** the expired/ineligible discount is not honored.
3. **Given** an idempotency key already used for a different item list or normalized coupon, **When** it is retried, **Then** checkout returns the existing conflict behavior without charging a different total or mutating stock.
4. **Given** a later catalog or promotion change, **When** an order is read, **Then** its saved promotion snapshot and totals remain unchanged.

### User Story 4 - Ask the assistant about real offers and coupon eligibility (Priority: P2)

An authenticated shopper can ask for available offers, category/product discounts, whether a coupon can be used, why it is ineligible, or the cart total after discount. The assistant calls the promotion/cart pricing services and presents only their results.

**Why this priority**: The existing assistant has a deterministic promotions intent but must be connected to commerce truth before it can answer discount questions.

**Independent Test**: Exercise assistant requests with a deterministic database fixture and assert route, typed operation, returned authoritative data, ownership, and zero promotion claims sourced from RAG or model text.

**Acceptance Scenarios**:

1. **Given** current active offers, **When** the shopper asks what is available, **Then** only currently active offers eligible for that shopper and requested product/category context are returned.
2. **Given** a coupon question, **When** the assistant checks the code, **Then** it returns the promotion service's eligibility and reason without mutating the cart unless the shopper explicitly asks to apply it.
3. **Given** an explicit apply or remove request, **When** the assistant performs the typed operation, **Then** the cart service confirms the mutation and the response includes the resulting authoritative cart price.
4. **Given** a prompt requesting an invented percentage, code, eligibility, expiry, or total, **When** no matching authoritative result exists, **Then** the assistant does not invent one and uses the defined no-offer or unsupported response.
5. **Given** a question about a discount, **When** the request is handled, **Then** RAG is not consulted for price/eligibility and any optional model explanation is constrained to returned promotion results.

### User Story 5 - Validate promotion behavior with repeatable local data (Priority: P1)

An engineer can seed deterministic synthetic promotion cases and run offline evaluation scenarios through real service boundaries without paid providers or production data.

**Why this priority**: Window, scope, rounding, stacking, and isolation errors are difficult to validate with ad hoc fixtures alone.

**Independent Test**: Run the versioned promotion evaluator against a positively identified local/test database and require every promotion scenario to pass.

**Acceptance Scenarios**:

1. **Given** the same synthetic seed manifest, **When** it is applied repeatedly, **Then** promotion records and their ownership markers are deterministic and unrelated records remain unchanged.
2. **Given** expired, future, threshold, category, product, percentage, fixed, user-targeted, and conflicting records, **When** the evaluator runs, **Then** each result matches the documented time, scope, integer-cent, and winner rules.
3. **Given** a request for a secret or unsupported discount, **When** evaluated, **Then** no promotion is fabricated.
4. **Given** an environment not positively identified as local/test with a loopback database, **When** seed/reset/evaluation is requested, **Then** it fails closed without changing data.

## Promotion Invariants

- **PROMO-001 - No invention**: A discount exists only when produced by persisted promotion data and deterministic evaluation; neither client nor assistant/model/RAG may invent it.
- **PROMO-002 - Time window**: Only `active` records with `starts_at <= now < ends_at` can apply or appear as currently available. Timestamps are timezone-aware UTC; evaluation receives an injectable aware clock.
- **PROMO-003 - Determinism**: Identical promotion records, user, cart/order lines, coupon, and evaluation time produce identical eligibility, reason, discount, and selection.
- **PROMO-004 - Structural scope**: All/category/product scope and pre-discount minimum-cart threshold are checked against canonical product IDs/categories and integer-cent cart context, never text similarity.
- **PROMO-005 - Shopper scope**: A promotion with a shopper restriction is eligible only when its eligible user matches the authenticated owner supplied by backend dependencies. Membership tiers are not modeled in v1.
- **PROMO-006 - No stacking**: At most one promotion applies per cart/order in v1. Select the eligible result with the greatest discount; ties prefer the explicitly entered coupon, then lexicographically smallest promotion ID. No discount is compounded.
- **PROMO-007 - Integer money**: All product prices, thresholds, discounts, subtotals, and totals use integer USD cents. Percentage discounts are whole-number percentages; calculate `floor((base_cents * percent + 50) / 100)` (half-up to the nearest cent), then cap by scoped subtotal and optional maximum discount.
- **PROMO-008 - Backend totals**: Only backend services calculate payable totals. The client may send item identifiers, quantities, and a coupon code for re-evaluation, never subtotal/discount/total values used by checkout.
- **PROMO-009 - Assistant explanation**: Assistant promotion statements may reference only returned authoritative results. An LLM, if used for wording, receives those results and cannot change them; deterministic wording is preferred.
- **PROMO-010 - Safe codes**: Normalize bounded coupon input by trim and uppercase; unknown/malformed codes fail with a generic safe error, without leaking whether unrelated private/user-targeted promotions exist or overwriting an existing valid cart code.

## Functional Requirements

- **FR-001**: Persist promotion name/description, optional normalized code, type/value, active flag, timezone-aware start/end, optional minimum cart amount and maximum discount, explicit all/category/product scope, and optional eligible shopper using validated constraints.
- **FR-002**: Enforce code uniqueness case-insensitively; enforce scope-target consistency, supported canonical product categories, valid value ranges, nonnegative thresholds, positive maximum discounts, and `ends_at > starts_at`.
- **FR-003**: Provide deterministic evaluation results containing promotion ID when known, `eligible`, stable reason code, `discount_cents`, and applied scope; unknown codes return a safe result without revealing private promotion data.
- **FR-004**: Calculate each discount only over matching line subtotals, apply the pre-discount whole-cart threshold, cap fixed/percentage discounts at the applicable subtotal and configured maximum, and prevent a negative final total.
- **FR-005**: Return active available promotions filtered by current time, shopper eligibility, and optional canonical product/category context; future, expired, inactive, or other-shopper-only promotions are not exposed as available.
- **FR-006**: Persist at most one normalized coupon code request on the shopper-owned cart; applying/removing it requires authentication and CSRF protection and always returns a newly calculated quote.
- **FR-007**: Extend the cart response with selected promotion details, coupon eligibility/reason where applicable, discount total, and final total while retaining the current integer-cent `subtotal` contract for existing consumers. Recalculate after every cart/coupon mutation and on every read; never persist a discount amount on the cart.
- **FR-008**: Re-evaluate all candidates at checkout in the existing order transaction using current locked products and authenticated user. Persist order subtotal, discount, final total, and an immutable promotion snapshot; include the normalized coupon in the idempotency request hash.
- **FR-009**: Preserve current stock locking, idempotency, ownership, auth, CSRF, cache behavior, and order history boundaries. Order totals and promotion snapshots are immutable after placement.
- **FR-010**: Extend deterministic assistant routing for browse/check/apply/remove promotion operations, validate bounded typed inputs, inject the current user server-side, and call existing promotion/cart pricing services only. No arbitrary SQL or direct model/database tool access is allowed.
- **FR-011**: Assistant browse/filter/check responses use current promotion results; apply/remove mutations require explicit shopper intent and return the service-confirmed cart. Promotion answers do not use RAG; no model or provider can set a discount, code, eligibility, date, or total.
- **FR-012**: Emit privacy-safe structured promotion operation logs containing only the request ID and bounded promotion metadata: operation, promotion ID or one-way coupon hash, eligibility, reason code, discount cents, duration, and status. Omit cart and user IDs by default. If a cart identifier is ever required operationally, it MUST be pseudonymous and non-reversible, and its use MUST be explicitly justified in a future specification. Do not log raw prompts, auth headers, secrets, payment data, or unnecessary coupon text.
- **FR-013**: Extend deterministic local seed data with active percentage/fixed, expired, future, threshold, category, product, shopper-restricted, and competing offers, preserving existing seed-owned identities and reset protections. Use no RAG document as a promotion source.
- **FR-014**: Extend the production-like evaluator to cover active offer listing; category scope; valid/unknown/expired/future coupons; below/above threshold; exact percentage rounding; fixed-discount cap; deterministic conflict resolution; cart mutation recalculation; owner isolation; and invented-discount resistance.
- **FR-015**: Add backend unit, API integration, checkout/idempotency, and security tests plus frontend/API tests for coupon apply/remove and authoritative displayed totals. Use test fixtures and deterministic providers only.
- **FR-016**: Provide a browser flow using synthetic users that signs in, finds/adds a laptop, checks offers, applies a valid coupon, verifies the server total, rejects invalid/expired coupons safely, mutates the cart and observes recalculation, removes the coupon, and proves a second user cannot access the first user's state. No flow may produce a 500/503.
- **FR-017**: Preserve the existing service/repository/API layering and add no external dependency, public promotion administration API, membership system, payment-method targeting, redemption counter, or stacking support unless the inspected implementation proves it is required and separately justified.

## Edge Cases

- Inactive, future, expired, exact-end-boundary, malformed timezone, or naive-time records fail closed and never yield a discount.
- Unknown/inactive/wrong-user coupon codes return a generic safe error; details for a shopper-restricted promotion are not exposed to another shopper.
- Product/category scope with no matching lines returns an ineligible result and zero discount; unknown categories are rejected at write/validation time.
- Minimum cart total is evaluated against the entire cart subtotal before discount; discount base is only the eligible scoped subtotal.
- A fixed value or percentage result greater than the scoped subtotal is capped; zero subtotal yields zero discount.
- Cart items, quantity, product activity/price, promotion active flag, scope, or time may change after a quote; cart reads and checkout recalculate.
- A selected coupon may become ineligible after a cart mutation; report its reason and use any remaining eligible automatic candidate under the winner rule.
- Equal discounts, overlapping scopes, duplicate item lines, zero/negative values, and integer overflow are deterministic or rejected before mutation.
- Cross-user cart IDs, coupon state, promotion eligibility, or assistant conversations are not accepted as authority.
- An idempotent checkout retry with the same normalized code returns the same order snapshot; a different code conflicts.

## Out of Scope

Public/admin promotion CRUD, campaign authoring UI, stacking, membership tiers, payment-method discounts, usage caps/redemption accounting, payment integration, client-computed totals, RAG-backed offers, LLM-created codes/percentages, deployment, production-data access or mutation, and new infrastructure/dependencies.

## Success Criteria

- **SC-001**: Every cart and order amount can be reproduced exactly from integer-cent product lines and the documented deterministic rule without floating-point arithmetic.
- **SC-002**: No expired, future, inactive, wrong-scope, or wrong-shopper promotion produces a discount in API, assistant, or checkout scenarios.
- **SC-003**: Every cart response includes subtotal, selected promotion results, discount total, and nonnegative final total derived by backend services after reads and mutations.
- **SC-004**: Checkout returns and persists totals/snapshot recalculated from current backend records; client-supplied totals are rejected or ignored and never affect the order.
- **SC-005**: All listed deterministic promotion evaluator scenarios pass without a paid model/provider; a prompt requesting a secret discount produces no invented offer.
- **SC-006**: Authenticated cart/coupon/assistant operations show no cross-user reads or mutations; invalid coupon input fails safely without leaking private eligibility.
- **SC-007**: The browser promotion journey completes with no HTTP 500/503 and shows the same final total returned by the backend.
- **SC-008**: Applicable backend migration, focused/full pytest, Ruff, Black, compileall, frontend Jest, TypeScript, lint, Prettier, build, evaluator, and browser gates pass or have an explicit evidence-based limitation recorded.

## Key Entities

- **Promotion**: Authoritative offer definition, public or optionally restricted to one shopper, with a bounded code, date window, type/value, scope, thresholds, and optional maximum discount.
- **Cart**: Existing shopper-owned item collection plus an optional coupon code request; discount amounts are never persisted on it.
- **Promotion Evaluation**: Deterministic result for one promotion and current user/cart context, including eligibility, reason, cents, and scope.
- **Order Pricing Snapshot**: Immutable subtotal, discount, total, and selected promotion details recorded at order placement.

## Assumptions

- Existing `Product.price`, cart subtotal, and order line values are integer USD cents despite legacy field names; API compatibility keeps the cart `subtotal` field in cents.
- Existing canonical categories are the only valid category scope values.
- Promotion records are written only by trusted backend operations. This increment does not expose an administrative write API.
- A coupon may be applied to a user's cart, but cart and order ownership remains derived from the authenticated session.
- The existing checkout request continues to identify product IDs and quantities. It may additionally submit a coupon code, but never prices or totals.
- No unresolved product, security, or user-flow decisions remain for v1.
