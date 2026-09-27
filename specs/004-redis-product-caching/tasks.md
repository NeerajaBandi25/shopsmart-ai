# Tasks: Redis-Backed Product Catalog Caching

**Input**: Design documents from `/specs/004-redis-product-caching/`

**Status**: Implementation and validation tasks for the scoped catalog cache.

## Phase 1: Cache Configuration and Boundary

- [ ] T001 Add positive `PRODUCT_CATALOG_CACHE_TTL_SECONDS` settings and a lazy shared async Redis client closed by FastAPI lifespan.
- [ ] T002 Add deterministic product response serialization, namespace/generation/pagination cache keys, TTL, fail-open Redis operations, and catalog service fallback.
- [ ] T003 Route the unchanged public product catalog operation through the catalog service without changing response fields or query semantics.

## Phase 2: Invalidation and Tests

- [ ] T004 Invalidate the catalog generation after a successful checkout stock transaction commits; do not invalidate on replay or failed checkout.
- [ ] T005 Add cache/service tests for key construction, hits, misses/fill, TTL expiry, parameter separation, invalid payloads, Redis read/write failures, and repository errors.
- [ ] T006 Preserve product catalog API integration coverage and verify checkout invalidation ordering and API fallback when Redis is unavailable.

## Phase 3: Documentation and Verification

- [x] T007 Document the server-side TTL, optional Redis behavior, Compose Redis default, and invalidation boundary.
- [x] T008 Run focused and database-independent backend tests, changed-file lint/format checks, security gates, dependency audit, and final diff audits.
- [ ] T009 Run Docker Compose and live Redis verification when the Docker CLI is available.

**Validation notes**: The complete suite passed 148 tests using SQLite, with five PostgreSQL-only tests skipped and one PostgreSQL row-locking test deselected because SQLite cannot verify `FOR UPDATE` behavior. A separate PostgreSQL-configured run could not create tables because its test role lacks privileges on schema `public`. Docker Compose/live Redis validation remains pending because the Docker CLI is unavailable.