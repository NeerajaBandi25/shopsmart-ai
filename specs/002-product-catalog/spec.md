# Product Catalog MVP

**Status**: In progress
**Scope**: First usable shopping journey slice: browse persisted products from the ShopSmart storefront.

## User-visible behavior

- Visitors can open the catalog without signing in and browse active products, newest first.
- Each product shows its name, description when present, price in dollars (API stores integer cents), and stock availability.
- Visitors can request additional pages; invalid page sizes are rejected. Empty catalogs and API failures have distinct UI states.
- Inactive products are never exposed by the public catalog.

## API and data contract

- `GET /api/v1/products?skip=0&limit=24` is public and returns `{ "items": Product[], "skip": number, "limit": number }`.
- `Product` exposes `id`, `name`, `description`, `sku`, `price` (integer cents), `stock_quantity`, and `max_purchase_quantity`; it does not expose write operations.
- `skip` is non-negative; `limit` is between 1 and 100. Defaults are 0 and 24.
- Product rows are persisted in PostgreSQL and queried through the existing repository. A migration creates the missing table; schema changes remain migration-managed.

## Acceptance criteria

1. A migrated database can persist product rows and serve the public catalog endpoint.
2. The endpoint returns active products in deterministic newest-first order and honors bounded pagination.
3. Inactive products are omitted; invalid pagination returns 422; an empty result returns an empty `items` list.
4. The storefront renders product data from the API and distinct loading, empty, and error states without requiring authentication.
5. Existing authentication flows and all four required CI checks remain unchanged.

## Tests

- Backend migration/schema and API integration tests cover populated, inactive, empty, paginated, and invalid-query cases.
- Frontend component/page tests cover product rendering, empty state, and request failure.
- Run the focused tests, then the existing backend and frontend CI commands.

## Explicitly deferred

Cart, checkout, orders, payment processing, product administration, and AI/RAG are not part of this slice; assess them next as separate MVP increments. No Phase 6B workflow or authorization prototype changes are in scope.
