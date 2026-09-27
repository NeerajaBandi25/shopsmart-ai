# Feature Specification: Redis-Backed Product Catalog Caching

**Feature Branch**: `feature/004-redis-product-cache`

**Status**: Draft

**Input**: Cache successful public product catalog reads in Redis without changing the existing API contract or PostgreSQL fallback.

## User Scenarios & Testing

### User Story 1 - Browse With a Warm Catalog Cache (Priority: P1)

A visitor requests a public catalog page that is already cached and receives the same page data without another repository query.

**Independent Test**: A cache-hit service test returns a validated response and proves the product repository is not called.

### User Story 2 - Browse When the Cache Is Cold or Unavailable (Priority: P1)

A visitor receives the existing database-backed catalog result on a miss or Redis failure; a successful miss populates the cache, while a failed write does not fail the request.

**Independent Test**: Cache-miss and Redis-failure tests verify repository calls, cache fill attempts, and successful fallback responses.

### User Story 3 - See Catalog Stock After Checkout (Priority: P1)

After a successful checkout commits inventory changes, later public catalog reads do not reuse pages cached before that transaction.

**Independent Test**: Checkout tests prove invalidation occurs after committed stock changes and not on an idempotent replay.

## Functional Requirements

- **FR-001**: Only the public `GET /api/v1/products` operation may read or populate this cache; authenticated and user-specific data MUST NOT be cached.
- **FR-002**: The request parameters, response fields, defaults, validation, active-product filtering, newest-first ordering, and pagination semantics MUST remain unchanged.
- **FR-003**: Cache keys MUST use the stable `shopsmart:product-catalog:v1` namespace and include every current response-affecting query parameter (`skip` and `limit`) plus an invalidation generation.
- **FR-004**: Only a successfully retrieved and validated `ProductPageResponse` may be cached. Error responses and repository failures MUST NOT be cached.
- **FR-005**: The cache TTL MUST be configurable by the server-only `PRODUCT_CATALOG_CACHE_TTL_SECONDS` environment setting, default to 60 seconds, and reject non-positive values.
- **FR-006**: Redis misses, malformed entries, connection/read errors, write errors, and timeouts MUST fail open to the existing PostgreSQL-backed repository behavior.
- **FR-007**: Cache payloads MUST use deterministic JSON serialization and be validated against the catalog response schema when read.
- **FR-008**: Successful checkout stock mutations MUST invalidate cached pages after the database commit. A cache invalidation failure MUST NOT fail checkout.
- **FR-009**: Redis configuration and credentials MUST remain server-side and MUST NOT be exposed to browser code.
- **FR-010**: No product-management API or database migration is introduced. Direct database product edits are visible within the configured TTL.

## Edge Cases

- Different `skip` or `limit` values never share a cached entry.
- Empty successful catalog pages may be cached.
- Invalid cached JSON or a response that does not validate is treated as a miss and refreshed from PostgreSQL.
- A generation change racing a cache lookup must not return an entry from an older generation.
- If Redis is unconfigured or unavailable, the existing catalog response and validation behavior remains available from PostgreSQL.

## Assumptions

- The current catalog accepts only `skip` and `limit`; future response-affecting filters/sorts must be added to the cache key and tests.
- Redis remains optional. PostgreSQL is authoritative.
- The existing login rate limiter uses a synchronous Redis client and has no reusable async client manager; the catalog uses one lazy process-wide async client with bounded socket timeouts and FastAPI shutdown cleanup.
- Checkout is the only application API path that mutates product data (stock). Product create/update/delete repository helpers are not exposed as application routes.

## Out of Scope

Product administration, cache warming, Redis as a source of truth, frontend changes, Compose/CI policy changes, deployment changes, browser/manual validation, payment behavior, and AI/RAG.

## Acceptance Criteria

1. Existing product catalog integration tests continue to pass with the same response shape, pagination, validation, active filtering, and ordering.
2. Unit tests cover cache key construction, valid hits, misses and writes, TTL expiration, parameter separation, malformed payloads, Redis read/write failure, database error non-caching, and generation invalidation.
3. Checkout invalidates catalog pages only after stock-changing transaction commit; idempotent replay and failed checkout do not invalidate.
4. With Redis unconfigured/unavailable, the public catalog still returns the database-backed response; cache failures do not turn successful database reads into API errors.
5. Existing CI policy, Compose service topology, frontend behavior, and API contracts are unchanged.