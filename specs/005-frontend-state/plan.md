# Implementation Plan: Frontend Client State

## Summary

Add Zustand as a narrowly scoped client-state primitive for a derived cart item count. The store is in-memory only and contains no cart lines, product data, order data, request status, or cached server responses.

## Technical Context

- Frontend: existing Next.js App Router, React, TypeScript, Jest, React Testing Library, and same-origin BFF API clients.
- Store: Zustand 5 with `cartItemCount`, `syncCartCount(cart)`, and `clearPrivateCommerce()`.
- Authority: cart pages and checkout retain their local API-returned cart data. The shared count is reduced from successful cart responses only.
- Session boundary: auth API success for login/logout/password change and 401 responses from auth, cart, or order clients clear the in-memory projection.
- UI: the existing authenticated Cart navigation link displays the count with a corresponding accessible name.
- Constraints: no additional state or query/cache library, persistence middleware, optimistic updates, backend/Redis/BFF changes, or commits/pushes/PRs.

## Data Flow

1. Existing component calls the current same-origin cart API client.
2. On successful response, the component keeps using the returned cart locally and synchronizes only the sum of item quantities into Zustand.
3. The authenticated navigation subscribes only to `cartItemCount`.
4. A successful identity/session transition or a 401 clears the client-only projection.

## Project Structure

- `frontend/src/lib/commerce-store.ts`: minimal in-memory Zustand store.
- `frontend/src/lib/*-api.ts`: existing API clients retain transport responsibility and clear state on 401.
- `frontend/src/components/AddToCartButton.tsx`, `CartPage.tsx`, and `CheckoutFlow.tsx`: synchronize the projection from successful cart responses.
- `frontend/src/components/nav.tsx`: displays the shared count in the existing Cart link.
- Colocated Jest tests cover store actions, API session boundaries, and UI integration.

## Validation

Run focused store/API/component tests and the complete frontend Jest suite; run `tsc --noEmit`, the existing Next lint script, Prettier checks on changed frontend files, a prohibited-library reference search, and Git diff/status audits confirming only Feature 005 files changed.
