# Architecture

`HomepageService` returns database category counts, active non-private offers and three interleaved 15-product editorial shelves. The visible storefront keeps compact card limits. `frontend/src/components/home/HomePageExperience.tsx` also asks the public product API for up to 100 in-stock rows so the guided hero can form an in-budget shortlist beyond the initial shelf rows. The service reads up to 1,500 orderable image-backed records before interleaving; larger catalogs deserve SQL-side selection.

`backend/src/schemas/product.py` derives delivery/highlights/gallery from the record's `specifications._presentation` metadata. `frontend/src/components/product-detail/VariantSelector.tsx` searches the same category/brand and groups names before the comma; each option links to an independent product ID. A future explicit product-family foreign key would be more robust than the naming convention.

`frontend/src/components/ShoppingTools.tsx` uses native dialogs for commands and comparison. Only public product IDs persist in sessionStorage; reopening comparison re-fetches current facts. The shortlist never authorizes prices or cart ownership.

The storefront uses Next.js App Router and React components. Browser requests go to same-origin `/api` route handlers. These proxy selected headers and cookies to the FastAPI address configured with `API_INTERNAL_URL`.

FastAPI routes validate contracts and inject a database session and authenticated shopper. Services hold commerce invariants; repositories perform SQLAlchemy queries. PostgreSQL persists users, sessions, products, carts, promotions, orders, documents and conversations. Alembic manages migrations; do not substitute automatic table creation for migrations.

`ProductCatalogService` optionally caches default catalog pages in Redis. Filtered searches query the repository directly. Checkout invalidates catalog cache after stock changes.

`CartService` obtains current product values and promotion quotes. `OrderService` owns checkout transactions, stock locks, user-scoped idempotency, price recalculation and historical snapshots. Browser prices are never trusted as order totals.

Key paths:

- `frontend/src/app/api/_commerce-proxy.ts`
- `backend/src/api/v1/deps.py`
- `backend/src/services/product_catalog_service.py`
- `backend/src/services/order_service.py`
- `backend/src/database.py`
- `backend/migrations/versions/`

This is a modular monolith with a separate web tier, not a microservice estate. Shared services let assistant and conventional UI actions enforce the same rules.
