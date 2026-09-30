# Feature Specification: Frontend Client State

**Feature Branch**: `feature/005-frontend-state`

**Status**: Implemented

**Input**: Add a small shared client-state foundation for commerce UI using Zustand, without introducing a server-state cache or changing the existing BFF/API boundary.

## User Scenarios & Testing

### User Story 1 - See Cart Count Across the Storefront (Priority: P1)

A shopper can see the current item quantity in the authenticated navigation after the cart has been loaded or changed through existing cart operations.

**Independent Test**: Component tests verify cart count synchronization from successful cart responses, preservation after failed mutations, checkout cleanup, and display in the authenticated cart link.

### User Story 2 - Keep Private Client State Session-Bound (Priority: P1)

Private commerce UI state is cleared after login, logout, password change, or an API response that establishes that the authenticated session is invalid.

**Independent Test**: Auth, cart, and order API-client tests verify projection clearing at successful session boundaries and on 401 responses.

## Functional Requirements

- **FR-001**: Zustand MUST be the only state-management library added for this feature; no query/cache library is added.
- **FR-002**: The store MUST contain only the derived private cart item count and the actions required to synchronize or clear it; it MUST NOT persist data.
- **FR-003**: Existing BFF/API responses MUST remain authoritative for cart, order, catalog, and checkout data.
- **FR-004**: Cart count MUST be synchronized only after successful cart API responses; failed cart operations MUST NOT optimistically change it.
- **FR-005**: Authenticated navigation MUST expose the current count through the existing Cart link.
- **FR-006**: Private commerce state MUST be cleared on successful login, logout, or password change, and when an auth, cart, or order API response returns 401.
- **FR-007**: Catalog and order-history fetching MUST remain in their existing API/BFF flows; no server-state cache is introduced.
- **FR-008**: Backend, Redis, BFF routes, checkout business logic, CI/security policy, and unrelated application behavior MUST remain unchanged.

## Edge Cases

- Empty cart responses replace the count with zero.
- A failed cart mutation leaves the last count unchanged unless the response is a 401, which clears private state.
- Checkout continues to use the existing order response and idempotency key; cart cleanup retains its all-settled behavior and only reflects successful remove responses.
- Login failure and non-401 API failures do not clear state through a successful session boundary.

## Out of Scope

Other state-management libraries, server-state caching, persistence, optimistic cart updates, backend or Redis changes, BFF route changes, catalog/order-history migration, and manual browser validation.

## Acceptance Criteria

1. The store holds no cart or order records and is not persisted.
2. Add-to-cart, cart load/update/remove, and checkout cleanup synchronize count only from successful cart responses.
3. Auth/session invalidation clears the projection without changing existing API request contracts.
4. The authenticated Cart link announces and displays the count.
5. Existing catalog and order-history API flows remain unchanged.
6. Focused and full frontend tests, TypeScript, lint, formatting, dependency, and diff-boundary checks pass.
