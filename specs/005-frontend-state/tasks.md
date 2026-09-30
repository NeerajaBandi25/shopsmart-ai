# Tasks: Frontend Client State

**Input**: Design documents from `/specs/005-frontend-state/`

**Status**: Implementation tasks for the Zustand-only client state increment.

## Phase 1: Store Foundation

- [x] T001 Add Zustand to the frontend manifest and lockfile.
- [x] T002 Add the non-persistent cart-count store and focused action tests.

## Phase 2: API and Session Boundaries

- [x] T003 Clear private commerce state on auth 401 and successful login, logout, and password change; test the auth boundaries.
- [x] T004 Clear private commerce state on cart and order 401 responses; test same-origin API behavior remains intact.

## Phase 3: Commerce UI Integration

- [x] T005 Synchronize cart count from successful AddToCartButton and CartPage responses; verify failed mutations do not optimistically alter it.
- [x] T006 Synchronize checkout cart reads and successful cleanup responses while preserving the existing checkout/idempotency flow.
- [x] T007 Display the count accessibly in the existing authenticated Cart navigation link.

## Phase 4: Documentation and Verification

- [x] T008 Document the client-state contract, data authority, boundaries, exclusions, and acceptance criteria.
- [x] T009 Run all frontend tests, TypeScript, lint, Prettier, dependency/reference, and diff-boundary checks; record results before commit/PR.
