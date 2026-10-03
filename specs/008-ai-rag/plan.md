# Architecture Plan: ShopSmart Commerce Assistant and Backend Knowledge RAG

**Branch**: `feature/ai-provider-governance-hardening`

**Spec**: [spec.md](./spec.md)
**Status**: Approved direction; implementation in progress

## Product Architecture

`Browser -> Next.js same-origin BFF -> FastAPI -> auth/policy dependencies -> deterministic intent router -> bounded orchestration -> existing commerce services OR backend-owned policy retrieval -> provider gateway only when useful -> grounded response and citations`.

The assistant is an orchestration surface over existing application services, not a second catalog/cart/order implementation. Dynamic data never enters retrieval as an authority. RAG remains for stable ShopSmart-owned knowledge. Existing customer-owned document ingestion may remain for internal/test use but is removed from the normal assistant page.

## Existing Capability Inventory

- Catalog: `ProductCatalogService` plus `ProductRepository`; search applies active state, canonical nullable category, text terms, minimum/maximum integer-cent price, and in-stock constraints in SQL. Product fields also include name, description, SKU, stock quantity, max purchase quantity, and active state. Legacy non-seeded products remain category-unknown unless an operator can establish a trustworthy category; no brand, variant, sale-price, or product-metadata schema exists, and there is no promotion engine.
- Cart: `CartService` validates availability, quantities, current prices, and ownership via injected user ID; cart routes require session, and mutations require CSRF. Cart items are unique per cart/product and require quantity >= 1.
- Checkout/orders: `OrderService` owns transactional checkout and returns current-user orders; order route scopes by session user. Orders preserve status text and immutable line-item snapshots, but there is no status-transition, shipping, returns, or refund service.
- Auth/BFF: same-origin Next.js auth and commerce routes forward server-only `API_INTERNAL_URL`, session cookies, and CSRF headers; backend dependencies remain the authorization authority.
- AI/RAG: `ChatService`, owner-scoped `RetrievalService`, `DocumentIngestionService`, `ProviderGateway`, classification governance, citation and eval infrastructure already exist. Current documents are user-owned; backend-owned policy corpus support is a required boundary.
- Redis: product catalog cache is optional and degrades to PostgreSQL; assistant tools call existing catalog service rather than bypassing cache policy.
- Observability: existing structured logging and bounded metrics are reused; no prompt, token, cookie, or document-content logging.

## Production-like Local Validation Data

- Catalog target: 1,000 products with stable generated UUIDs, namespaced SKUs, and canonical structured categories (`laptops`, `phones`, `accessories`, `footwear`, `fashion`, `appliances`, `home`, `beauty`, `groceries`). Category is assigned by deterministic seed data, not inferred from descriptions. Price, stock (including zero/low/available), purchase limits, and active state use existing constraints.
- Local accounts: deterministic synthetic IDs and `.invalid` email addresses; password hashes use the repository's existing password utility. Credentials are documented as local-only and never represent production secrets or people. Loyalty/premium membership is not modeled and is reported as a gap.
- Cart/order scenarios: create records with existing ORM models and ownership relations. Seed empty/single/multi/quantity-update carts and users with no/multiple orders. Out-of-stock validation is exercised as a rejected service action, not an invalid cart row. Order status coverage is illustrative persisted history only, not a claim that transitions are implemented.
- Seed ownership: a versioned manifest uses deterministic UUIDv5 identities and reserved `SYNTH-EVAL-V1-` SKUs, `@shopsmart.local.invalid` emails, and `local-eval-v1-` knowledge source keys. Existing collisions with those reserved identities fail closed unless both identity and expected seed marker match. Reset deletes only these marked entities and refuses if dependencies imply non-seeded references; it does not truncate or broadly clear tables. No database migration is needed for this ownership scheme.
- Environment guard: require explicit local/test mode and seed opt-in, reject production-like environment labels, and require a loopback database host before opening a session. The command does not create schema; migrations remain separately managed.
- Knowledge: publish a small, deterministic set of clearly labeled local validation policies via `KnowledgeIngestionService`, including source key/title/category/content/version and provenance. These synthetic policies are local fixtures, not approved business policy for production.
- Evaluation: a versioned dataset records expected intent, supported price/text filters, scenario/user role, and assertions for comparison, cart/order state, policy citations/no-evidence, ownership and injection/override negatives. Run through service/API contracts and the authenticated browser/BFF; keep the existing small fixture evals for fast regression tests.
- Performance: measure catalog search, assistant turn, cart query, order query, and policy retrieval against the seeded database. Existing cart reads join cart items/products; order history uses select-in item loading. Product-reference resolution currently loads up to 20 products individually, and policy retrieval ranks the complete active knowledge corpus in process; record these as scale observations rather than optimizing before measurement.

## Routing and Tool Design

Add a pure deterministic intent router with typed intent/slot outputs. A scoped assistant orchestration service accepts the authenticated user ID and existing SQLAlchemy session. It parses only supported, bounded filters/references and selects a single route/tool or explicit no-op response.

Tool adapters delegate to existing services/repositories under their existing contracts:

- Catalog adapters use `ProductCatalogService`/`ProductRepository`; category, price, and availability filters are SQL predicates before text candidate ranking. Category parsing uses a deterministic alias allowlist; unknown/ambiguous category requests never degrade to text search. Conversation result IDs are populated only from these validated results. Brand/RAM filters remain unsupported.
- Cart adapters call `CartService`; identity is injected, not parsed from text/model output. Mutations require an explicit action and product reference from the user's persisted conversation results.
- Order adapters call `OrderService.get_user_orders`; IDs must be matched against the current user's returned order list. Report only stored status; do not invent shipment tracking.
- Promotion adapter is a typed capability boundary. Since no promotion service/model exists, return the specified no-active-offer response until an authoritative implementation is separately introduced.
- Policy adapter calls backend-owned knowledge retrieval, then the existing `ProviderGateway` with policy classification and source metadata. User-owned documents are excluded from customer assistant retrieval.

## Backend-Owned Knowledge Boundary

Retain deterministic chunking, embeddings, retrieval, gateway, citations, and evaluations. Introduce distinct server-owned source/version/chunk ownership or an equivalently explicit corpus scope; never fake a system user or disable owner predicates. Curated sources are packaged/admin-published content. Ingestion is authenticated/authorized outside customer routes, versioned, idempotent, and evaluable. User upload endpoints remain isolated as internal/test capability until an admin authorization model exists.

## Conversation Context

Persist bounded routing context as user-owned conversation state. Store product IDs from each search result, plus source timestamp/version, in conversation state or bounded message metadata. Follow-up resolution uses only the current user's conversation and re-fetches every entity through its authoritative service before use. Expired/missing references produce a safe clarification, never arbitrary lookup.

## UI and API

Replace the upload-led assistant UI with a commerce conversation, compact suggested prompts, message history, and composer. Same-origin BFF continues to forward cookies and CSRF. Display only user-facing answer, product/card data from tool results, and policy citations where used. Keep upload/admin/testing outside primary navigation. Provider, model, classification internals, raw retrieval scores, and database IDs are not user-facing.

## Data Model and Migration

Add an additive migration for nullable `products.category`, canonical-value check constraint, and category index. Do not infer/backfill categories for existing rows; they remain `NULL` until trusted catalog data is available. Seed-owned products are assigned canonical values and reset/reseeded safely. Continue explicit knowledge-corpus ownership/versioning and bounded conversation result references. Proposed knowledge records: `KnowledgeSource` (stable identifier/title/category/active version), `KnowledgeVersion` (content hash/publish status), and `KnowledgeChunk` (version, chunk index, text, embedding, source provenance/classification). Records are server-owned; no user ID is accepted from the assistant. Add constraints/indexes and migration tests.

## Evaluation Design

Extend deterministic offline evals with intent cases for every supported intent; route/tool and argument assertions; zero provider/RAG-call expectations for deterministic paths; exact product text/price/stock checks; no-promotion correctness; cart authorization and order ownership; policy retrieval recall, groundedness, citation correctness, and no-answer; injection, provider override, cross-user, stale reference, and unauthorized identifier tests. Add a separate versioned production-like data set and report dataset cardinality and per-path timing. Use controlled fixtures and mocked providers.

## Delivery Order

1. Update spec, architecture plan, tasks, project instructions, and eval requirements.
2. Add intent/typed request-result contracts and deterministic tests.
3. Implement non-mutating catalog/cart/order/promotion/policy orchestration against existing services.
4. Add guarded cart actions and user-scoped product-result context.
5. Separate backend-owned policy knowledge from customer-owned upload/retrieval; add a migration only if required by discovery.
6. Replace assistant UI, retain same-origin BFF, and hide customer upload.
7. Expand evals, run backend/frontend gates, and validate browser flows/security.
8. Add the guarded local production-like seed/reset utility, realistic assistant eval set, and synthetic owned-knowledge corpus; do not add unsupported commerce models.

## Risks and Explicit Limitations

No hierarchical category taxonomy, promotion engine, variant model, loyalty status, or order-transition service exists. A bounded canonical category field is authoritative for category filters; old rows with unknown categories are excluded from category-constrained results rather than guessed. Validation must report the remaining gaps and must not synthesize dynamic answers. Preserve the catalog's integer-cent contract. Do not add a new AI package or service. External model calls remain governed by the existing provider registry/classification policy.
