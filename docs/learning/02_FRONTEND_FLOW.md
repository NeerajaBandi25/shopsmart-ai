# Frontend flow

**New discovery path:** `getHomepage()` consumes `/api/homepage` for database categories, shelves and public offers. `frontend/src/components/ShoppingTools.tsx` provides Ctrl/Cmd+K and a comparison tray. Only public IDs persist in sessionStorage; each comparison opening refreshes product facts. `frontend/src/components/product-detail/VariantSelector.tsx` links real sibling SKUs, rather than changing a price locally.

**What:** Page components render catalog, product detail, cart, checkout, orders, and assistant results.

**Why:** Typed APIs prevent components from turning model text or display values into commerce records.

**How / request flow:** Components call the API helpers. Next.js route handlers forward selected cookies, CSRF and idempotency headers to the internal API; private responses use no-store.

**Key files:**

- `frontend/src/lib/api-client.ts`
- `frontend/src/lib/cart-api.ts`
- `frontend/src/lib/order-api.ts`
- `frontend/src/app/api/_commerce-proxy.ts`
- `frontend/src/components/ProductCatalog.tsx`
- `frontend/src/lib/commerce-store.ts`

**Interview talking points:** The browser does not need the internal backend URL. Zustand stores the cart badge, while authoritative cart data stays on the server.
