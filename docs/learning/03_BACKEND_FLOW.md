# Backend flow

**Homepage flow:** `backend/src/services/homepage_service.py` counts active database categories, interleaves orderable image-backed products and lists active public offers. It does not expose private coupon eligibility or claim measured popularity. `backend/src/api/v1/product_routes.py` exposes this public merchandising endpoint.

**What:** FastAPI routes validate request schemas and obtain a database session and authenticated user where required.

**Why:** Domain rules belong in services so browser and assistant actions share them.

**How / request flow:** Request → dependency validation → route → service → repository → SQLAlchemy async session → response. get_db rolls back failures; services decide when to commit.

**Key files:**

- `backend/src/main.py`
- `backend/src/api/v1/deps.py`
- `backend/src/api/v1/product_routes.py`
- `backend/src/services/product_catalog_service.py`
- `backend/src/repositories/product_repository.py`
- `backend/src/database.py`

**Interview talking points:** Show how filtered search bypasses the unfiltered Redis page cache. Never return an unfiltered cache hit for a constrained query.
