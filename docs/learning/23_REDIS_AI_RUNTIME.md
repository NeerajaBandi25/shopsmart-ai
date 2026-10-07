# 23. Redis AI runtime

Redis is an optional acceleration and coordination layer. PostgreSQL and domain services remain authoritative for product price and stock, cart totals, promotions, preferences, orders, and policy-source versions. Redis loss cannot change those facts or authorize a purchase.

## Implemented roles

- **Model routing state:** `ModelRuntimeState` shares a rolling 15-minute event window for provider failures and 429s, short-lived health and circuit state, latency, and task-specific eval scores. The model catalog is cached for three minutes. Redis keys have bounded TTLs; without Redis, selection uses bounded process-local state and emits a degraded-state warning.
- **Login throttling and session/cache utilities:** the existing application limiter uses Redis when configured and retains durable login-attempt audit records in PostgreSQL. Session validation checks database ownership and expiry; cache loss does not grant access.
- **Shopping mission extraction:** a five-minute cache stores only typed, owner-scoped extraction results. It does not cache catalog results or user commerce facts.
- **Product catalog response cache:** the existing short-lived catalog cache is an optimization only; current service authorization and catalog state determine responses.

## Deliberately not implemented

Provider concurrency throttling is not a second Redis limiter; provider quotas are governed by the gateway policy and observed rate-limit state. Conversation history stays in PostgreSQL. Recommendation rankings and policy/RAG retrieval have no Redis cache because there is no measured need to trade cache invalidation complexity for latency. Cart, promotion, and order operations use transactional database rules and their existing idempotency constraints; they are never served from Redis. No stale authoritative commerce result may be used after a cache hit.

## Failure and recovery checks

Validate Redis with an isolated database index. Check a mission cache miss then hit, expiry, Redis-down extraction, catalog refresh, rolling 429/failure ratios, circuit open after repeated failures, and recovery after the circuit TTL. Do not flush a shared instance. Runtime smoke records and removes only uniquely namespaced temporary keys. Test commerce correctness separately with Redis disabled to prove it continues from PostgreSQL.

The adaptive state keys and their TTLs are documented in [adaptive model routing](../../backend/ADAPTIVE_MODEL_ROUTING.md).
