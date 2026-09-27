# Tasks: Same-Origin Commerce BFF

**Input**: Design documents from `/specs/003-commerce-bff-boundary/`

**Status**: Implementation tasks for the scoped commerce BFF increment.

## Phase 1: BFF Routes and Contracts

- [x] T001 Add a server-only commerce proxy and thin same-origin product, cart, checkout, and order handlers in `frontend/src/app/api/`.
- [x] T002 Add route contract tests for query/body/header forwarding, Cookie/CSRF/idempotency, Set-Cookie, upstream statuses, and safe 503 behavior in `frontend/src/app/api/commerce-routes.test.ts`.

## Phase 2: Browser Client Migration

- [x] T003 Migrate catalog requests to `/api/products` in `frontend/src/lib/api-client.ts` and cover same-origin URL construction in `frontend/src/lib/api-client.test.ts`.
- [x] T004 Migrate cart retrieval and mutations to `/api/cart/*` in `frontend/src/lib/cart-api.ts` and add coverage in `frontend/src/lib/cart-api.test.ts`.
- [x] T005 Migrate checkout and order history to `/api/orders/*`, retaining CSRF and idempotency behavior, and add coverage in `frontend/src/lib/order-api.test.ts`.

## Phase 3: Documentation and Verification

- [x] T006 Document server-only backend configuration and same-origin commerce paths in `frontend/README.md` and `frontend/.env.example`.
- [x] T007 Run focused commerce tests, existing frontend checks, relevant backend commerce tests, TypeScript, lint, formatting, and direct-URL/diff audits; record outcomes before declaring ready for commit/PR.
