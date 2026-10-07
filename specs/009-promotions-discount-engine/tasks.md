# Tasks: ShopSmart Promotions and Discount Engine

**Input**: Design documents in `specs/009-promotions-discount-engine/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/http-and-assistant.md`

**Organization**: Tasks are grouped by the user stories in `spec.md`. The request explicitly requires unit, integration, security, evaluator, frontend, and browser validation, so test tasks are included and precede their implementation.

**Safety**: No task authorizes commit, push, PR creation, deployment, branch/worktree deletion, or production-data access/mutation.

## Phase 1: Setup and Schema Foundation

**Purpose**: Add the minimal persistent entities while preserving current checkout/history and metadata behavior.

- [x] T001 Add the Promotion SQLAlchemy entity with code, time window, type/value, scope, thresholds/cap, optional eligible user, indexes, and database constraints in `backend/src/models/promotion.py`.
- [x] T002 Add the optional normalized coupon code to Cart and order subtotal/discount/snapshot fields to Order in `backend/src/models/cart.py` and `backend/src/models/order.py`.
- [x] T003 Register Promotion with Alembic and test metadata in `backend/migrations/env.py` and `backend/tests/conftest.py`.
- [x] T004 Add additive migration 013 for promotions, cart coupon state, order snapshot fields/backfill, indexes, and constraints in `backend/migrations/versions/013_promotions_discount_engine.py`.

## Phase 2: Foundational Promotion Evaluation

**Purpose**: Establish tested deterministic eligibility and pricing shared by cart, checkout, and assistant.

- [x] T005 [P] Add unit tests for date boundaries, UTC-awareness, scope, threshold, shopper restriction, code normalization, reason codes, percentage rounding, fixed caps, zero protection, and no-stacking tie breaks in `backend/tests/unit/test_promotion_service.py`.
- [x] T006 Implement promotion lookup and canonical code resolution in `backend/src/repositories/promotion_repository.py`.
- [x] T007 Implement deterministic evaluation, quote calculation, active offer listing, and typed results in `backend/src/services/promotion_service.py`.

## Phase 3: User Story 1 - Accurate Cart Price and Available Offers (Priority: P1)

**Goal**: Return current server-owned subtotal, selected promotion, discount, and nonnegative final cart total; recalculate after each read/mutation.

**Independent Test**: Seed test products/promotions and assert cart amounts and selection exactly match independently computed integer cents across matching/mismatching scopes, thresholds, windows, and two users.

- [x] T008 [P] [US1] Add cart pricing integration tests for automatic offers, product/category scope, threshold changes, empty cart, and cross-user isolation in `backend/tests/integration/test_cart_api.py`.
- [x] T009 [US1] Route cart line totals and reads through PromotionService and preserve the existing cents-valued `subtotal` contract in `backend/src/services/cart_service.py`.
- [x] T010 [US1] Extend cart response schemas with coupon evaluation, selected promotion, discount cents, and final total in `backend/src/api/v1/cart_routes.py`.
- [x] T011 [US1] Verify cart mutations recalculate using current product and promotion rows and never store a discount amount in `backend/tests/unit/test_cart_service.py`.

## Phase 4: User Story 2 - Apply, Check, and Remove Coupon (Priority: P1)

**Goal**: Allow the current shopper to store one coupon request, safely reject invalid codes, and remove a code without trusting cached totals.

**Independent Test**: Exercise authenticated, CSRF-protected coupon apply/remove against valid, unknown, expired, future, wrong-user, wrong-scope, and threshold cases; verify invalid attempts do not overwrite existing state.

- [x] T012 [P] [US2] Add API tests for valid apply/remove, generic invalid-code errors, CSRF/auth rejection, retained prior code, and shopper isolation in `backend/tests/integration/test_promotions_api.py`.
- [x] T013 [US2] Implement owner-scoped coupon persistence, normalization, safe failures, remove behavior, and fresh quote responses in `backend/src/services/cart_service.py`.
- [x] T014 [US2] Add typed `POST /cart/coupon` and `DELETE /cart/coupon` routes with authenticated user and CSRF dependencies in `backend/src/api/v1/cart_routes.py`.
- [x] T015 [P] [US2] Add same-origin coupon proxy routes in `frontend/src/app/api/cart/coupon/route.ts`.
- [x] T016 [US2] Extend Cart types and add CSRF-protected apply/remove calls in `frontend/src/lib/cart-api.ts`.
- [x] T017 [US2] Add accessible coupon input, eligibility feedback, remove control, applied-offer list, discount, and total to `frontend/src/components/CartPage.tsx`.
- [x] T018 [P] [US2] Test coupon states, recalculation feedback, loading/error handling, and owner-safe client behavior in `frontend/src/components/CartPage.test.tsx` and `frontend/src/lib/cart-api.test.ts`.

## Phase 5: User Story 3 - Fresh Checkout Price and Immutable Order Snapshot (Priority: P1)

**Goal**: Re-evaluate promotion eligibility from current locked products in the existing idempotent checkout transaction and persist exact order pricing details.

**Independent Test**: Change a promotion/cart condition after quoting, check out using an optional coupon code, and prove the resulting order snapshot is recalculated, immutable, and idempotent only for the same items and normalized code.

- [x] T019 [P] [US3] Add service/API tests for checkout expiry/scope re-evaluation, order subtotal/discount/snapshot, changed-code idempotency conflict, replay, and rollback in `backend/tests/unit/test_order_service.py` and `backend/tests/integration/test_order_checkout.py`.
- [x] T020 [US3] Recalculate promotions inside the locked checkout transaction, hash normalized coupon with item lines, and persist immutable pricing snapshot in `backend/src/services/order_service.py`.
- [x] T021 [US3] Accept only optional bounded coupon code and expose snapshot totals while rejecting client pricing fields in `backend/src/api/v1/order_routes.py`.
- [x] T022 [US3] Send the server-returned cart code, never totals, through checkout and render authoritative order/quote totals in `frontend/src/lib/order-api.ts`, `frontend/src/components/CheckoutFlow.tsx`, and `frontend/src/components/CheckoutForm.tsx`.
- [x] T023 [P] [US3] Test checkout coupon forwarding, order totals, and immutable success rendering in `frontend/src/components/CheckoutFlow.test.tsx` and `frontend/src/components/CheckoutForm.test.tsx`.

## Phase 6: User Story 4 - Assistant Answers from Promotion Results (Priority: P2)

**Goal**: Route offer browse/check and explicit coupon apply/remove to typed backend services only; do not retrieve RAG for discount truth.

**Independent Test**: Run deterministic assistant requests with mocked/provider-call assertions and verify each price/eligibility value equals the promotion/cart service result.

- [x] T024 [P] [US4] Add route tests for active-offer questions, laptop scope, read-only `Can I use SAVE10?`, explicit apply/remove, and invented-discount prompts in `backend/tests/unit/test_assistant_router.py`.
- [x] T025 [US4] Add deterministic `COUPON_APPLY` and `COUPON_REMOVE` routing and bounded code/category extraction in `backend/src/services/assistant_router.py`.
- [x] T026 [P] [US4] Add assistant tests proving service calls, no mutation for read-only checks, no RAG/provider pricing, correct total, safe invalid response, and user isolation in `backend/tests/unit/test_commerce_assistant.py`.
- [x] T027 [US4] Connect PROMOTIONS, COUPON_APPLY, and COUPON_REMOVE to available/evaluate/apply/remove/cart pricing services in `backend/src/services/commerce_assistant.py`.
- [x] T028 [US4] Render authoritative offer, coupon evaluation, and discounted cart result data in `frontend/src/app/assistant/page.tsx` and cover it in `frontend/src/app/assistant/page.test.tsx`.

## Phase 7: User Story 5 - Synthetic Promotion Data and Offline Evaluation (Priority: P1)

**Goal**: Seed deterministic representative cases and require all promotion scenarios to pass in the existing local/test evaluator.

**Independent Test**: Run unit seed ownership tests and then the production-like evaluator against an explicitly verified local/test loopback database, with all scenario keys true.

- [x] T029 [P] [US5] Add repeatability, promotion collision, reset ownership, and unrelated-row preservation tests in `backend/tests/unit/test_production_like_seed.py`.
- [x] T030 [US5] Add deterministic active percentage/fixed, expired, future, threshold, category, product, user-targeted, and competing promotion entries to `backend/src/seed/production_like_v1.json` without changing product/user IDs.
- [x] T031 [US5] Build, upsert, validate ownership, and safely reset only deterministic seed-owned promotions in `backend/src/seed/production_like.py`.
- [x] T032 [P] [US5] Add routing and promotion evaluator cases A-M, including code validity, thresholds, exact math, winner selection, mutation, user isolation, and injection resistance in `backend/evals/datasets/commerce_production_like_v1.json`.
- [x] T033 [US5] Exercise real PromotionService, CartService, OrderService, and CommerceAssistantService for every new scenario in `backend/src/evals/production_like.py` and report pass counts.

## Phase 8: Cross-Cutting Validation and Independent Review

**Purpose**: Complete privacy-safe logging, full validation, browser flow, and the ten requested design/security challenges.

- [x] T034 [P] Add bounded promotion log fields to the JSON allowlist and emit safe operation/result/duration logs without raw codes or prompts in `backend/src/core/observability.py` and `backend/src/services/promotion_service.py`.
- [x] T035 [P] Test log allowlisting and prove raw coupon, prompt, credentials, and payment data are absent in `backend/tests/unit/test_observability_logging.py` and `backend/tests/unit/test_promotion_service.py`.
- [x] T036 Run the promotion evaluator and complete the synthetic browser journey. Local desktop/mobile browser work covers offer lookup, coupon apply, unknown/expired rejection, quantity repricing, removal, owner-specific order rendering, and a second-shopper switch proving coupon/cart isolation. A desktop browser checkout also created an authoritative pending order/payment through an isolated fake provider and verified order history; Playwright fulfilled the Stripe-shaped destination locally, so no external Stripe session or charge was created.
- [x] T037 Run migration graph/SQL checks, focused and full pytest, Ruff, Black, and compileall in `backend/` against isolated test resources only.
- [x] T038 Run focused/full Jest, TypeScript, lint, scoped Prettier, and Next.js build for `frontend/` without mass-formatting unrelated files.
- [x] T039 Review all ten PROMO invariants and the independent questions in `specs/009-promotions-discount-engine/spec.md`; record findings and resolve any legitimate defect in its owning source/test files.
- [x] T040 Review `git diff --check`, changed-file scope, and final worktree against the quickstart. Commit/push only the explicitly authorized milestone to the existing branch; do not create a new PR, merge, or deploy.

## Dependencies and Execution Order

- Schema/model registration and migration (Phase 1) block all service stories.
- Promotion repository/evaluator (Phase 2) blocks cart pricing, checkout, assistant, and evaluator integration.
- US1 cart pricing precedes coupon UI and is reused by checkout and assistant.
- US2 coupon persistence and endpoints precede checkout coupon forwarding and assistant mutation tools.
- US3 checkout snapshot depends on the promotion service and cart coupon contract.
- US4 assistant integration depends on promotion/cart APIs but does not modify promotion calculation.
- US5 seed/eval work depends on the model/service contracts and can be developed after them.
- Cross-cutting browser/full-suite/review tasks run after all implementation stories.

## Parallel Opportunities

- Model/migration tests and pure evaluator tests can be prepared independently once field contracts are fixed.
- Separate frontend cart and assistant tests can proceed after API response contracts stabilize.
- Seed manifest work and assistant routing fixtures touch separate files and can proceed independently after service semantics are fixed.
- Do not parallelize edits to shared `cart_service.py`, `commerce_assistant.py`, `order_service.py`, `assistant_router.py`, or `production_like.py`; each has one writer at a time.

## Implementation Strategy

1. Complete schema and deterministic evaluator; prove unit math/time/scope rules.
2. Deliver server-priced cart offers and coupon operations; validate US1/US2 independently.
3. Integrate checkout re-evaluation and immutable snapshots without weakening stock locking/idempotency.
4. Integrate assistant tools and deterministic no-invention responses.
5. Extend guarded synthetic seed/evaluator, then run browser, full backend/frontend gates, and independent review.
6. Stop after local validation. Do not commit, push, create a PR, merge, deploy, or touch production data.
