# Feature Specification: Same-Origin Commerce BFF

**Feature Branch**: `feature/003-commerce-bff-boundary`

**Status**: Draft

**Input**: Route browser-facing catalog, cart, checkout, and order-history requests through the same-origin Next.js BFF already used for authentication.

## User Scenarios & Testing

### User Story 1 - Browse the Public Catalog (Priority: P1)

A visitor can browse the public product catalog using the storefront without the browser calling FastAPI directly.

**Independent Test**: Catalog pagination reaches the existing products API through a same-origin route and preserves product data and validation errors.

### User Story 2 - Manage the Authenticated Cart (Priority: P1)

A signed-in shopper can retrieve their cart, add items, change quantities, and remove items. Existing server-side ownership, inventory checks, and response behavior remain unchanged.

**Independent Test**: BFF route tests verify cookie forwarding for reads, cookie and CSRF forwarding for mutations, and pass-through of upstream results and errors.

### User Story 3 - Checkout and Review Orders (Priority: P1)

A signed-in shopper can submit checkout with its CSRF token and idempotency key, then view their order history through same-origin routes.

**Independent Test**: Route tests verify checkout forwards Cookie, X-CSRF-Token, Idempotency-Key, and body unchanged, and order history forwards Cookie.

## Functional Requirements

- **FR-001**: Browser catalog, cart, checkout, and order-history calls MUST use same-origin Next.js API routes.
- **FR-002**: Backend service URLs MUST be read only by server-side code from `API_INTERNAL_URL` and MUST NOT be exposed to browser code.
- **FR-003**: Authenticated requests MUST forward the incoming session Cookie; cart mutations and checkout MUST forward `X-CSRF-Token`.
- **FR-004**: Checkout MUST preserve the existing request body and `Idempotency-Key` header.
- **FR-005**: BFF responses MUST preserve upstream status, safe response body, content type, relevant rate-limit/request-id headers, and Set-Cookie headers.
- **FR-006**: Network failure or missing internal backend URL MUST return a generic 503 response without exposing upstream internals.
- **FR-007**: Existing API contracts, product availability, cart behavior, checkout validation/idempotency/inventory behavior, order authorization, and authentication behavior MUST remain unchanged.
- **FR-008**: No backend commerce business logic or unrelated state-management, cache, payment, deployment, observability, or AI/RAG infrastructure is added.

## Edge Cases

- Upstream errors including 401, 403, 404, 409, 422, 429, and 5xx retain their status and safe error envelope.
- Empty/no-content upstream responses remain no-content.
- Invalid product IDs and invalid request bodies continue to be rejected by the existing backend contract.
- Missing `API_INTERNAL_URL` or backend transport failure returns the generic BFF 503 response.

## Assumptions

- FastAPI route and security contracts on `origin/main` remain authoritative.
- The existing `/api/auth/csrf` route remains the browser's same-origin CSRF-token source.
- Product catalog reads are public; cart/order reads require the session cookie; cart mutations and checkout require session and CSRF validation.
- Checkout idempotency remains enforced by FastAPI using the existing `Idempotency-Key` contract.

## Out of Scope

Redis, React Query, Zustand, AWS deployment, payment processing, backend commerce logic changes, observability infrastructure, AI/RAG, CI policy, and manual browser validation.

## Acceptance Criteria

1. No browser-facing call for catalog, cart, checkout, or order history targets FastAPI or reads `NEXT_PUBLIC_API_URL` to construct its request URL.
2. Same-origin BFF tests cover all new routes, cookies, CSRF, idempotency, Set-Cookie propagation, error statuses, and safe service failure.
3. API-client tests cover all migrated operations and verify same-origin paths, credentials, and required headers.
4. Existing authentication behavior and commerce component behavior remain covered by their current automated tests.
