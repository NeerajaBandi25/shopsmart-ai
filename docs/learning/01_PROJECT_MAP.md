# Project map

**What:** ShopSmart combines a Next.js storefront, a FastAPI API, PostgreSQL persistence, optional Redis catalog caching, and a policy-controlled AI gateway.

**Why:** Each layer has one job: the UI presents state, services enforce business rules, repositories query records.

**How / request flow:** Next.js page → same-origin route handler → FastAPI route → service → repository → database.

**Key files:**

- `frontend/src/app`
- `frontend/src/components`
- `backend/src/api/v1`
- `backend/src/services`
- `backend/src/repositories`
- `backend/src/models`

**Interview talking points:** Explain a vertical slice instead of listing every framework. Start with adding a product and follow it to the database.
