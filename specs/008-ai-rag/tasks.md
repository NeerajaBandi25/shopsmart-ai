# Feature 008 Tasks: Commerce Assistant and Backend Knowledge RAG

## Product Contract

- [x] T001 Update Feature 008 spec with commerce role, all required intents, source authority, tools, governance invariants, response text, and eval criteria.
- [x] T002 Update architecture plan with existing service inventory, backend-owned RAG boundary, known promotion/catalog limitations, UI/API boundaries, and delivery order.
- [x] T003 Keep task map and project instructions aligned with the product direction.

## Intent and Orchestration

- [x] T004 Add deterministic typed intent routing for GREETING, HELP, PRODUCT_SEARCH, PRODUCT_COMPARE, PROMOTIONS, CART_QUERY, CART_ACTION, ORDER_QUERY, POLICY_QUERY, SUPPORT_QUERY, and UNSUPPORTED.
- [x] T005 Add bounded user-scoped orchestration contracts and response templates; test no unnecessary provider/RAG calls.
- [x] T006 Add authoritative catalog search/details/compare adapters over existing services; exact price/stock filters must be structural and only supported fields may be claimed.
- [x] T007 Add promotions adapter with truthful no-active-offer behavior until an authoritative promotion service exists.
- [x] T008 Add current-user cart/order read adapters over existing services; test ownership and not-found behavior.
- [x] T009 Add explicit typed cart mutations with current-user injection, prior-result reference validation, and normal CSRF enforcement.
- [x] T010 Persist bounded conversation product references or equivalent user-scoped context and reject stale, arbitrary, and cross-user identifiers.

## Backend-Owned Policy RAG

- [x] T011 Define server-owned knowledge source/version/chunk storage and migration; do not use a fake user or mix customer-owned and policy corpora.
- [x] T012 Reuse normalization, chunking, embeddings, retrieval, provider gateway, classification policy, and citation provenance for ShopSmart-maintained policy content.
- [x] T013 Restrict existing customer upload flows to internal/admin/test usage and ensure assistant retrieval excludes customer-uploaded content.
- [x] T014 Add tests for policy retrieval, source-version citation, no evidence, injection, owner isolation, and provider classification.

## API and Frontend

- [x] T015 Integrate authenticated assistant route through existing FastAPI auth/CSRF dependencies and same-origin Next.js BFF.
- [x] T016 Replace document-upload assistant UI with a commerce conversation, suggested prompts, result/citation rendering, and empty/loading/error states.
- [x] T017 Keep document ingestion off the normal customer assistant page and primary navigation.
- [x] T018 Add frontend tests for assistant intent flows, authoritative result display, citation/no-answer, and auth/service errors.

## Evaluations and Verification

- [x] T019 Extend golden evals for every intent, route/tool/arguments, unnecessary RAG/provider calls, product filter/price/stock correctness, no-promotion, cart/order ownership, policy quality/citations/no-answer, injection, and identifier manipulation.
- [x] T020 Add deterministic tool/security evals using controlled fixtures and mocked providers; no paid API dependency.
- [x] T021 Run focused backend AI/commerce/security tests, full pytest, frontend Jest, TypeScript, lint, Prettier, build, migration, and browser E2E checks; record unavailable gates honestly.
- [x] T022 Perform independent review against AI-COM-001 through AI-COM-010; fix valid findings and rerun affected checks.
- [x] T023 Review changed-file scope and local browser flow; prepare the requested PR without merging or enabling auto-merge.

## Production-like Local Validation Dataset

- [x] T024 Add a versioned deterministic catalog manifest targeting 1,000 products using canonical structured categories, varied integer-cent prices, active state, and supported stock/quantity constraints; use deterministic IDs and reserved SKUs.
- [x] T025 Add synthetic local accounts with deterministic IDs and `.invalid` addresses plus empty/single/multi/update carts and multi-status order histories using existing models; no real identities, membership fields, or unsupported transitions.
- [x] T026 Implement guarded `seed` and `reset-seeded-data` commands that require local/test opt-in, reject non-loopback/production targets, fail on reserved-identity collisions, and touch only versioned seed-owned IDs. Add tests proving repeatability, reset ownership, refusal behavior, and unrelated-data preservation.
- [x] T027 Seed clearly labeled local-only ShopSmart knowledge sources through the existing server-owned ingestion service, with stable source keys, provenance, and idempotent active versions; do not represent synthetic local policies as production-approved policy.
- [x] T028 Add a versioned production-like assistant eval dataset covering required commerce, policy, multi-turn, no-result, injection/provider override, and cross-user cases; extend deterministic scoring and exercise real existing service/BFF paths where available.
- [x] T029 Implement and test supported multi-turn comparison/reference behavior required by the production-like eval (including cheaper-result selection and resolving “that one” only from the same user's authorized conversation results).
- [x] T030 Run and record local catalog/assistant/cart/order/policy latency, dataset counts, browser E2E outcomes, schema/capability gaps, and security/reset checks; do not optimize without measured evidence.

## Structured Category Correction

- [x] T031 Add nullable canonical `Product.category`, check constraint, index, and additive migration; leave existing unclassified products `NULL`.
- [x] T032 Extend the repository/catalog search contract with controlled category and min/max price filters applied structurally before text matching; unknown categories must not fall back to text.
- [x] T033 Parse common category aliases deterministically and persist only validated result IDs for compare/cheaper/cart follow-ups.
- [x] T034 Assign canonical categories to every production-like seed product without changing deterministic IDs; test description cross-mentions and unknown-category behavior.
- [x] T035 Add category-precision assertions for laptop/phone queries, unrestricted generic price search, category-safe multi-turn mutation, and privacy-safe structured search logs.
- [x] T036 Apply the migration to the local PostgreSQL database, reset only marked seed data, reseed, report category distribution, and run the real-database evaluator and browser flow.
