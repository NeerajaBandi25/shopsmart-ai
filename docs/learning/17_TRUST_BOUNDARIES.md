# Trust boundaries

**What:** ShopSmart separates public catalog data, authenticated shopper state, provider-bound AI evidence, and server-side commerce mutations.

**Why:** A browser or generated answer can be stale or manipulated, so neither is an authority for identity, stock, discounts, or order totals.

**How / request flow:** The Next.js same-origin handlers forward only selected cookies and mutation headers to FastAPI. FastAPI resolves the session from its database and binds mutations to that user; state-changing browser requests also require the matching session CSRF token. Services reload products and compute promotion quotes. The checkout service locks product rows, verifies current stock, recalculates totals, and persists order snapshots transactionally. Assistant commerce output uses these same service results. AI evidence carries a classification; provider governance uses the highest classification among request and evidence.

**Key files:**

- `frontend/src/app/api/_commerce-proxy.ts`
- `backend/src/api/v1/deps.py`
- `backend/src/core/session_validator.py`
- `backend/src/services/cart_service.py`
- `backend/src/services/order_service.py`
- `backend/src/services/ai_governance.py`
- `backend/src/services/ai_gateway.py`

**Interview talking points:** CSRF proves a request came from a page with the session token; it does not grant ownership. Session ownership and service-level checks do that. An idempotency key makes a retry replay the same order only when its request payload matches.
