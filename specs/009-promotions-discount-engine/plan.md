# Implementation Plan: Promotions and Discount Engine

**Branch**: `feature/promotions-discount-engine` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Base**: `origin/main` at `9eb862a87c8bf87f3a9ecd0ffd99cd59ecf5693a`

**Input**: [Feature specification](spec.md)

## Summary

Add a backend-owned promotion record and deterministic evaluator shared by cart pricing, coupon operations, checkout, and assistant tools. Keep money in integer USD cents, evaluate current UTC windows and structural product/category/shopper rules, select at most one promotion, and persist the re-evaluated order price and promotion snapshot inside the existing checkout transaction. Extend the current local synthetic dataset and evaluator without changing seed-owned product/user IDs. No promotion truth comes from RAG, client totals, or model text.

## Technical Context

**Language/Version**: Python 3.11; TypeScript/Node 20

**Primary Dependencies**: Existing FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, Next.js 14, React 18; no new dependency

**Storage**: Existing PostgreSQL database; SQLAlchemy models and Alembic migration

**Testing**: pytest with SQLite unit fixtures and PostgreSQL integration tests; Jest/Testing Library; deterministic production-like evaluator; shared local browser flow

**Target Platform**: Existing Linux containers/local Windows development stack

**Project Type**: Existing full-stack web application (Next.js BFF + FastAPI)

**Performance Goals**: Avoid one query per cart line; load cart products and candidate promotions in bounded queries. Record local evaluator timing, with no unsupported latency SLA or premature optimization.

**Constraints**: Integer cents only; UTC-aware half-open time window; checkout recalculates inside existing inventory/idempotency transaction; auth and CSRF remain required; no client total authority; no RAG/model pricing; no production data or deployment; no new dependency.

**Scale/Scope**: Existing maximum 50 checkout lines; current local evaluator seeds 1,000 products. Promotion records are a small backend-managed set with indexed active/window/code/scope/user lookup. One code per cart; no stacking, usage limits, membership tiers, payment targeting, or public admin CRUD.

## Constitution Check

**Pre-research gate**: Pass. The design keeps one product, reuses existing repository/service/API boundaries, uses PostgreSQL/Alembic, preserves auth/CSRF and checkout transactions, avoids new dependencies, and tests business rules with deterministic fixtures.

**Post-design gate**: Pass. `PromotionRepository` owns reads; `PromotionService` owns deterministic eligibility and integer calculation; cart/order services remain the only pricing/transaction owners. Assistant tools receive typed service results and never access SQL or RAG for discounts. Seed/reset stays guarded and owned-record-only. No extra service, infrastructure, or policy change is introduced.

## Phase 0 Research

Decisions and alternatives are recorded in [research.md](research.md). Concrete entities and constraints are in [data-model.md](data-model.md); public and assistant contracts are in [contracts/http-and-assistant.md](contracts/http-and-assistant.md).

Key decisions: single best eligible discount with stable tie-breaking; percentage calculation `(base_cents * percent + 50) // 100`; all-cart threshold with scope-only discount base; stored coupon code but no stored cart discount; checkout snapshot; optional single-user targeting; no stacking or admin write API.

## Phase 1 Design

- Add `Promotion` with checked type/value/scope, canonical category/product target, UTC window, optional threshold/cap, optional owner-scoped user, and case-insensitive unique code.
- Add an optional normalized coupon code to `Cart`; never persist a quote or discount amount there.
- Extend `Order` with subtotal, discount, and immutable JSON promotion snapshot; backfill existing order subtotal from its unchanged total.
- Add migration 013 after `012_product_structured_category`; import the model in `backend/migrations/env.py` and the shared test metadata fixture.
- Add `PromotionRepository` and deterministic `PromotionService`; services accept an injected aware evaluation time for tests.
- Integrate cart reads/mutations, authenticated coupon apply/remove endpoints, same-origin BFF, existing cart UI, and fresh total display.
- Integrate checkout by adding only an optional coupon code to its typed payload; include normalized code in idempotency hash and recalculate from locked current products before writing order/item/snapshot.
- Extend assistant routing to `PROMOTIONS`, explicit `COUPON_APPLY`, and `COUPON_REMOVE`; use cart/promotion service methods, deterministic result wording, and no RAG retrieval.
- Extend allowlisted structured log fields only with safe bounded values; never log raw coupon or prompt.
- Extend the existing local-only seed manifest and reset identity checks with deterministic promotion IDs; extend offline and database-backed evaluator scenarios.

## Project Structure

### Documentation

```text
specs/009-promotions-discount-engine/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/http-and-assistant.md
├── checklists/requirements.md
└── tasks.md
```

### Backend

```text
backend/src/models/promotion.py
backend/src/models/cart.py
backend/src/models/order.py
backend/src/repositories/promotion_repository.py
backend/src/services/promotion_service.py
backend/src/services/cart_service.py
backend/src/services/order_service.py
backend/src/services/assistant_router.py
backend/src/services/commerce_assistant.py
backend/src/api/v1/cart_routes.py
backend/src/api/v1/order_routes.py
backend/src/core/observability.py
backend/src/seed/production_like.py
backend/src/seed/production_like_v1.json
backend/src/evals/production_like.py
backend/evals/datasets/commerce_production_like_v1.json
backend/migrations/versions/013_promotions_discount_engine.py
backend/migrations/env.py
backend/tests/unit/
backend/tests/integration/
backend/tests/evals/
```

### Frontend

```text
frontend/src/lib/cart-api.ts
frontend/src/lib/order-api.ts
frontend/src/components/CartPage.tsx
frontend/src/components/CheckoutFlow.tsx
frontend/src/components/CheckoutForm.tsx
frontend/src/app/assistant/page.tsx
frontend/src/app/api/cart/coupon/route.ts
frontend/src/app/api/orders/checkout/route.ts
frontend/src/components/*.test.tsx
```

**Structure Decision**: Extend the existing layered backend and same-origin BFF. No microservice or separate promotion frontend is justified.

## Validation Strategy

1. Unit tests prove date boundaries, deterministic scope/user/threshold reasons, coupon normalization, percent half-up rounding, fixed cap, zero protection, single-winner tie behavior, and invalid inputs.
2. API/integration tests prove authenticated CSRF mutations, cart ownership, cart recalculation, safe invalid codes, checkout re-evaluation, order snapshot immutability, idempotency hash semantics, and inventory rollback.
3. Assistant tests/evals prove deterministic intents/tools, authoritative offers, no mutation on read-only coupon checks, no RAG/provider pricing, no fabricated discount, and cross-user isolation.
4. Seed tests prove deterministic promotions, repeatability, collision refusal, reset ownership, and unrelated-row preservation.
5. Run migration history/offline SQL checks and apply the migration only to an explicitly verified disposable test database.
6. Run focused and full backend tests, Ruff, Black, compileall, frontend Jest, TypeScript, lint, scoped Prettier plus repository formatting gate where available, and build.
7. Run production-like evaluator and browser journey with synthetic local identities; observe no HTTP 500/503 and compare UI values to API results.
8. Perform the ten independent PROMO review questions from the request and review `git diff` for runtime/security boundaries. Do not commit, push, open a PR, deploy, or touch production data.

## Complexity Tracking

No constitution violations. The added promotion table/repository/service and order snapshot are required to make discount authority, evaluation, and historical totals independently auditable; no additional service, package, campaign system, or admin role is introduced.
