# Optional cache for default catalog pages

**Status:** Accepted

**Context:** Default product pages can be reused, but a cache hit must not erase search filters or continue advertising stock after checkout.

**Decision:** Redis is best-effort and optional. Only unfiltered, newest-first paginated catalog reads use the cache. Keys contain page bounds and a generation token. Filtered searches query the repository. After a committed checkout changes stock, the service advances the generation; database reads remain available when Redis is not configured or fails.

**Consequences:** Cache contents are disposable and cannot become the authority for filtered results. Checkout correctness does not depend on Redis availability. This cache strategy is scoped to catalog pages; it does not claim general invalidation for arbitrary direct database edits.

**Source:** `backend/src/services/product_catalog_service.py`, `backend/src/services/product_catalog_cache.py`, `backend/src/services/order_service.py`.
