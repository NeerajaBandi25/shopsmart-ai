# Product catalog flow

**What:** The catalog exposes public product discovery with search, structured filters, sorting, paging, images, and product details.

**Why:** The browser needs shareable discovery state, while product facts must stay grounded in the database and API.

**Flow:** URL parameters initialize `ProductCatalog`; the same-origin Next.js route validates and forwards the query to FastAPI. `ProductCatalogService` and its repository apply category, subcategory, brand, price, stock, and sort constraints before returning the page and count. Product detail fetches one active record and exposes its gallery/specifications.

**Key files:** `frontend/src/components/ProductCatalog.tsx`, `frontend/src/lib/catalog-query.ts`, `frontend/src/app/api/products/route.ts`, `backend/src/api/v1/product_routes.py`, `backend/src/services/product_catalog_service.py`, `backend/src/repositories/product_repository.py`.

**Important rules:** Prices and inventory are read from the backend. Filter state belongs in the URL. Paginate server-side; do not load the entire catalog into the browser.

**Common failure / debug:** If a filter returns no results, compare the URL parameters with `GET /api/v1/products` directly, then inspect repository predicates and stored category/specification values. Check the request ID in backend logs for API failures.

**Interview explanation:** Describe one filter from input to SQL query and explain how URL state makes the result shareable without making the browser authoritative.
