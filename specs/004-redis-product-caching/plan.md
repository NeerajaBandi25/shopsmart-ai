# Implementation Plan: Redis-Backed Product Catalog Caching

## Summary

Add best-effort Redis caching around the existing public product catalog repository call. Keep PostgreSQL authoritative, preserve `GET /api/v1/products` exactly, and fail open to the database whenever Redis is absent or fails.

## Technical Context

- Backend: FastAPI route -> catalog service -> existing `ProductRepository`; async SQLAlchemy and Redis 5.
- Current Redis use: login rate limiting uses a synchronous `redis.Redis` client; there is no shared async Redis client manager. Add one lazy `redis.asyncio.Redis` process client and close it from the existing FastAPI lifespan.
- Cache data: validated `ProductPageResponse` serialized to canonical compact JSON (`sort_keys=True`). Invalid payloads are treated as misses.
- Namespace: `shopsmart:product-catalog:v1`; a generation key invalidates all pages without scanning. Page keys contain generation, `skip`, and `limit`.
- TTL: positive `PRODUCT_CATALOG_CACHE_TTL_SECONDS`, default 60 seconds.
- Mutation path: checkout decrements stock. Advance cache generation only after commit and do not let invalidation failure fail checkout. Direct DB edits are bounded by TTL because no product-admin route exists.
- No API schema, repository ordering, migrations, Compose topology, CI policy, or frontend changes.

## Project Structure

- `backend/src/core/redis_client.py`: lazy async client getter and lifecycle cleanup.
- `backend/src/schemas/product.py`: existing public response schemas shared with the service/cache and route.
- `backend/src/services/product_catalog_cache.py`: key construction, validated JSON read/write, TTL, fail-open behavior, and generation invalidation.
- `backend/src/services/product_catalog_service.py`: cache-aside orchestration with the existing repository fallback.
- `backend/src/api/v1/product_routes.py`: delegate to the catalog service while retaining the current route signature and response model.
- `backend/src/services/order_service.py`: post-commit invalidation after a stock-changing checkout.
- Unit/integration tests, backend environment example/docs, and the Feature 004 Spec Kit artifacts.

## Validation

Run focused cache/config/checkout unit tests; existing product catalog integration tests; full backend pytest; Ruff and the existing backend security Ruff checks; formatting checks; Compose configuration/Redis ping when the existing service is available; an explicit unconfigured/unavailable Redis fallback test; and `git diff --check`. Confirm no migrations, frontend files, CI files, secrets, or generated outputs changed. Do not run browser/manual validation.