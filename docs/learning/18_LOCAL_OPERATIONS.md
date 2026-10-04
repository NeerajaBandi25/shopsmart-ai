# Local operations and readiness

**What:** FastAPI exposes separate liveness and database-readiness checks; PostgreSQL is the persistence target and Redis is optional.

**Why:** A process can be running while its database is unreachable, and optional cache failure should not disable catalog reads.

**How / request flow:** `/health` reports that the process responds. `/readiness` executes `SELECT 1` against the configured database and returns 503 if that check fails. Apply Alembic migrations before normal startup. `ProductCatalogService` uses Redis only for unfiltered newest-first pages; filtered catalog requests query the repository. Catalog cache invalidation advances a generation after checkout commits a stock change. Do not use automatic table creation as a substitute for migrations in a persistent environment.

**Key files:**

- `backend/src/main.py`
- `backend/src/database.py`
- `backend/src/core/config.py`
- `backend/src/services/product_catalog_service.py`
- `backend/src/services/product_catalog_cache.py`
- `backend/migrations/versions/`
- `backend/README.md`

**Interview talking points:** `/health` is not a database check. Unit and API tests using SQLite do not establish PostgreSQL locking behavior. See the current checkpoint in `.factory/status.md` for the tested branch state and database-specific skips.
