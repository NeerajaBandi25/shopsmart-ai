# Scalability

Homepage merchandising is bounded to a 1,500-record read before category interleaving in `backend/src/services/homepage_service.py`. This fits the portfolio catalog; a larger deployment should select shelves in SQL or materialize editorial selections. Configuration lookup currently uses product naming conventions; explicit family IDs would improve indexing and maintainability.

Existing foundations include async database access, bounded catalog pagination, optional Redis catalog pages, database constraints, conditional stock decrement, checkout idempotency and structured observability.

Measure before extending these foundations. Current limitations:

| Area               | Current behavior                                                          | Next step when justified                                   |
| ------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Retrieval          | Loads accessible chunks and ranks cosine similarity in application memory | Indexed vector search with ownership filters               |
| AI quota/metrics   | In-process counters; quota has no daily rollover                          | Shared atomic budgets with date buckets and monitoring     |
| Session validation | Updates and commits last activity for successful requests                 | Throttled activity writes preserving expiry semantics      |
| Catalog            | Default pages cached; filters query SQL                                   | Query plans, appropriate indexes and measured cache policy |
| Orders             | Shopper history loads orders and associated lines                         | Cursor pagination for large histories                      |
| Checkout           | Product row locks use stable ID ordering and protect inventory            | Load-test contention and connection-pool pressure          |
| Images             | Next.js image components with sizes/aspect containers                     | Measure LCP, transfer size and CDN/cache behavior          |

Horizontal web/API replication also requires shared configuration, a database connection budget and centralized telemetry. Redis unavailability should preserve catalog correctness through database fallback.

Do not quote throughput or Core Web Vitals without a recorded measurement. See `product_catalog_cache.py`, `assistant_knowledge.py`, `session_validator.py`, `ai_governance.py` and `order_repository.py` under `backend/src/`.
