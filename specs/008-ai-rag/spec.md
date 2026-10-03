# Feature Specification: ShopSmart Commerce Assistant and Backend Knowledge RAG

**Feature Branch**: `feature/ai-provider-governance-hardening`
**Status**: Implemented and validated for v1; PR #44 merged
**Roadmap scope**: Preserve embeddings, chunking, retrieval, grounded answers, citations, conversation history, provider abstraction, and evaluations. These capabilities serve ShopSmart commerce; Jev, a cloud vector store, paid providers, and unspecified Days 73-75 are not required.

## Product Role and User Value

ShopSmart AI is an authenticated commerce assistant, not a customer-document chat product. It helps shoppers discover and compare catalog products, check active offers, inspect their cart and orders, perform explicitly requested cart actions, and get grounded answers from ShopSmart-maintained policies and guides. Customers do not need to upload documents to use the assistant.

## User Scenarios and Testing

### User Story 1 - Discover and compare products (P1)

An authenticated shopper asks for products using exact constraints such as brand, category, price ceiling, availability, or supported attributes, then compares selected results. Exact constraints and displayed price/stock come from the catalog service. A follow-up such as "compare the first two" can reference only products returned to that same user's conversation.

### User Story 2 - Understand offers, cart, and orders (P1)

An authenticated shopper asks what offers are active, what is in their cart, or where an order is. Responses come from authoritative promotion/pricing, cart, or order services and are scoped to the current session user. Mutations require a typed action, CSRF validation at the API boundary, and a result confirmed by the cart service.

### User Story 3 - Get ShopSmart policy and support answers (P1)

An authenticated shopper asks about returns, refunds, shipping, warranty, payments, loyalty, FAQs, or buying guides. The assistant retrieves versioned ShopSmart-owned knowledge, answers only from retrieved evidence, and cites the actual policy source. Customer uploads are not part of this flow.

### User Story 4 - Continue a bounded conversation (P1)

A shopper can refer to the first products in a previous result or continue the current topic. Conversation state and resolved entity references are scoped to the authenticated user, bounded, and never accepted as arbitrary model-supplied identifiers.

### User Story 5 - Evaluate quality and safety (P1)

An engineer runs deterministic offline evals covering routing, tool choice/arguments, authoritative commerce facts, ownership, policy retrieval, citation/grounding, no-answer, provider policy, and injection resistance.

### User Story 6 - Validate with production-like local data (P1)

An engineer seeds a deterministic, realistic synthetic commerce dataset and evaluates the assistant through the normal authenticated application flow. The dataset includes varied catalog availability and prices, isolated test shoppers, representative carts and order histories, and versioned ShopSmart-owned policy knowledge. Regression/unit fixtures remain necessary but are not sufficient for product validation.

## Supported Intents

The deterministic router MUST classify each request as one of: `GREETING`, `HELP`, `PRODUCT_SEARCH`, `PRODUCT_COMPARE`, `PROMOTIONS`, `CART_QUERY`, `CART_ACTION`, `ORDER_QUERY`, `POLICY_QUERY`, `SUPPORT_QUERY`, or `UNSUPPORTED`. Routing uses bounded deterministic rules initially; no external LLM is required to classify an intent. Ambiguous or unsupported requests do not trigger a mutating tool.

## Data-Source Strategy and Authority

Dynamic and transactional facts MUST come from existing ShopSmart services/APIs and their authoritative PostgreSQL state: product price, availability, stock, active promotions/eligibility, cart, checkout, orders, and user-specific state. If a promotion/eligibility service does not exist or returns no applicable offer, the assistant MUST say it cannot find an active applicable offer; it MUST NOT infer or invent a discount.

Backend-maintained RAG is for stable ShopSmart knowledge: returns, refunds, shipping, warranty, payment guidance, loyalty, category/buying guides, and FAQs. RAG MUST NOT be authoritative for price, stock, discounts, cart, order status, or other transactional state.

Customer document upload is not part of the primary commerce UX. Any retained customer-owned ingestion endpoint is internal/admin/test-only and MUST NOT be presented as the normal assistant workflow. ShopSmart knowledge ingestion is server/admin-owned: `content source -> normalize -> chunk -> embed -> index -> version -> evaluate`.

## Production-like Validation Dataset

Unit and regression fixtures MUST remain focused and fast, but MUST NOT be the only evidence for product behavior. Assistant product validation MUST also use repeatable synthetic data at realistic enough cardinality and variety to exercise the real catalog, cart, order, conversation, and backend-owned knowledge paths through the normal services and BFF.

- The local catalog target is approximately 1,000 products, adjusted only when the implemented schema or laptop performance makes that scale inappropriate. Prices and available/low/out-of-stock states vary within fields and constraints that actually exist.
- Product category MUST be a normalized, authoritative structured field. Seeded products use canonical categories; existing records whose category cannot be reliably determined remain unknown rather than being guessed. Category, brand, color, size, storage/RAM, variant, sale-price, and metadata variety MUST otherwise use only implemented fields and authoritative behavior. Unsupported catalog dimensions MUST be reported as product gaps, not simulated in assistant answers.
- Synthetic local accounts cover new and returning shoppers; loyalty/premium status only when implemented; empty and populated carts; no-order and multi-order histories. Cart/order states, timestamps, totals, and ownership MUST satisfy actual model and service constraints.
- Promotions/discount scenarios are seeded only if an authoritative promotion capability exists. Otherwise, the gap is explicit and the assistant returns no applicable offer; RAG MUST NOT supply dynamic discount claims.
- Backend-owned RAG fixtures cover approved ShopSmart stable knowledge and retain source name, version, content, and provenance. They are not customer uploads and cannot override transactional facts.
- Every seed run is deterministic, repeatable, and limited to seed-owned records. A reset operation removes only records bearing the seed ownership marker; it never truncates tables or deletes unrelated developer data.
- Seed and reset operations are local-development/test-only and MUST fail closed in production or when the environment cannot be positively identified as non-production. Seed credentials and addresses are synthetic, documented as local-only, and never used for real people or production accounts.
- No real production customer data, copied PII, secrets, or production credentials may enter the validation dataset.

The versioned evaluation set MUST cover intent routing, exact price/category filters where supported, numeric boundaries and no-results, comparison, cart reads/mutations, order history and ownership, promotion capability/no-offer behavior, policy retrieval/citations/no-evidence, multi-turn reference resolution, cross-user isolation, malformed filters, out-of-stock/nonexistent products, unrelated questions, prompt injection, and provider/model override attempts. Dynamic answers are checked against the authenticated user's actual service results; policy answers are checked against cited backend-owned versions.

## Assistant Orchestration

`User -> Intent Router -> Auth/Policy -> Tool or RAG selection -> existing ShopSmart services -> Provider Gateway/LLM when useful -> grounding/citations -> response`.

Greeting/help and simple service results SHOULD be deterministic without an LLM call. The model may explain or format verified tool results, but may not author dynamic facts, choose its own provider/model, access a database, execute SQL, or perform a mutation outside a typed authorized tool. Tool results are the source of truth and are revalidated before presentation.

## Bounded Tool Interfaces

The orchestration layer exposes typed conceptual tools and reuses the existing service layer; it MUST NOT duplicate business logic:

- `search_products(filters)`, `get_product_details(product_id)`, `compare_products(product_ids)`
- `get_promotions(context)`
- `get_cart(user_id)`, `add_to_cart(user_id, product_id, quantity)`, `remove_from_cart(user_id, product_id)`
- `get_orders(user_id)`, `get_order_status(user_id, order_id)`
- `retrieve_policy_knowledge(query)`

Authenticated user IDs are injected by backend dependencies, never accepted from model output or client tool arguments. Product result references resolve from bounded, user-owned conversation context. Tool arguments are schema-validated and bounded. Mutations require explicit user intent and normal CSRF/API authorization.

## Governance Invariants

- **AI-COM-001**: Dynamic commerce facts come from authoritative services.
- **AI-COM-002**: RAG is never authoritative for price, stock, discounts, cart, or orders.
- **AI-COM-003**: Tool calls require authentication and resource ownership.
- **AI-COM-004**: The LLM cannot execute arbitrary database queries or access the database directly.
- **AI-COM-005**: Exact numeric filters are structurally applied to catalog results.
- **AI-COM-006**: Tool inputs are typed, validated, bounded, and safely errored.
- **AI-COM-007**: The model cannot override authentication, provider, model, or classification policy.
- **AI-COM-008**: Policy citations identify retrieved ShopSmart knowledge only.
- **AI-COM-009**: Conversation references resolve only to authorized prior results.
- **AI-COM-010**: Normal assistant use never depends on customer document uploads.
- **AI-COM-CAT-001**: Category constraints are enforced structurally against the authoritative product category field.
- **AI-COM-CAT-002**: Product name or description mentions cannot satisfy or override a category filter. A charger described as "compatible with laptops" is not a laptop.
- **AI-COM-CAT-003**: Category, price, availability, and other supported structured filters constrain the candidate set before optional text or semantic ranking.
- **AI-COM-CAT-004**: Multi-turn comparisons and cart references resolve only to product IDs in the validated result set for that user's conversation.
- **AI-COM-CAT-005**: Numeric constraints such as maximum price are applied structurally and remain true for every returned product.

Existing owner isolation, policy-first provider routing, external-provider classification enforcement, citation provenance, no arbitrary provider/model override, secure session cookies, CSRF, and server-authoritative data remain mandatory.

## Functional Requirements

- **FR-001**: Require an authenticated session for assistant commerce, conversation, policy, cart, and order operations; derive the user ID from the session.
- **FR-002**: Route the eleven supported intents deterministically and safely route ambiguous/unsupported requests without unauthorized tool calls or unnecessary provider calls.
- **FR-003**: Provide bounded typed adapters for catalog search/details/compare, promotions, cart read/mutation, order list/status, and policy retrieval by calling existing services/APIs.
- **FR-004**: Apply exact catalog filters (including numeric maximum price and availability) structurally before responding; use server-returned product price and stock only.
- **FR-005**: Return promotion results only from an authoritative promotion/eligibility service. When none is configured or applicable, return the defined no-promotion response without inventing discounts.
- **FR-006**: Enforce current-user ownership for cart, orders, conversations, and entity references; mutation requires explicit intent, typed arguments, service validation, and CSRF at the HTTP boundary.
- **FR-007**: Use backend-owned, versioned ShopSmart policy knowledge for stable facts. Customer upload is absent from normal assistant UI and any retained customer ingestion is clearly internal/admin/test-only.
- **FR-008**: Preserve deterministic bounded chunking/embeddings, owner isolation for customer-owned test data, grounded answer providers, and citations whose provenance maps to retrieved source/version/chunk.
- **FR-009**: Call the LLM/provider only when explanation or grounded policy generation needs it; greeting, help, structured results, and no-result responses use deterministic responses where sufficient.
- **FR-010**: Support bounded user-scoped conversation context for product-result references; reject stale, cross-user, unknown, or model-invented identifiers.
- **FR-011**: Use explicit responses: friendly commerce greeting; no-product, no-promotion, no-order, no-policy-evidence, auth-required, and service-unavailable wording. Normal no-result responses MUST NOT be reported as unsafe retrieved-content failures.
- **FR-012**: Record bounded routing/tool/retrieval/provider metrics without prompts, credentials, cookies, private content, or unnecessary personal data.
- **FR-013**: Provide reproducible offline evals for intent/route, tool/arguments, no unnecessary RAG/provider, commerce accuracy/ownership, policy recall/groundedness/citations/no-answer, and security/injection/provider override.
- **FR-014**: Preserve existing auth, governance, commerce, Redis, deployment, observability, provider gateway, and API contracts; use focused migrations only where the backend-owned knowledge model requires them.
- **FR-015**: Provide a deterministic, versioned local commerce dataset sized for realistic assistant validation (targeting approximately 1,000 products) and representative synthetic users, carts, orders, and supported catalog states, without introducing fields unsupported by the application.
- **FR-016**: Provide seed and reset operations restricted to positively identified local-development/test environments; both operations MUST be repeatable, and reset MUST delete only records explicitly owned by that seed dataset.
- **FR-017**: Keep all seeded identities synthetic and documented as local-only; reject real production PII, secrets, and copied production records from seed inputs.
- **FR-018**: Provide a versioned assistant evaluation set that exercises normal authenticated BFF and service paths, including multi-turn result references, commerce correctness, policy provenance, and cross-user/security negatives.
- **FR-019**: Report unsupported schema/capability dimensions, including promotions or product attributes where absent, rather than creating synthetic assistant behavior that implies those capabilities exist.
- **FR-020**: Measure baseline local catalog search, assistant, cart, order, and policy retrieval latency on the dataset and record the dataset size and environment; measurements are observational and MUST NOT trigger premature optimization.
- **FR-021**: Store product category in a normalized structured field, apply category filters in catalog SQL/service logic, parse only controlled category aliases, and return unsupported/no-result behavior for unknown categories without falling back to text-only matching. For example, "laptops under 60000" means `category=laptops AND price<=60000`; a charger whose description mentions laptops MUST NOT match.
- **FR-022**: Emit structured, privacy-safe product-search logs containing request ID, intent, operation, category, numeric filters, result count, duration, status, and error type for expected validation failures; never log full prompts, secrets, cookies, or private content.

## Response Behavior

- Greeting: "Hi! I can help you find products, compare options, check offers, manage your cart, track orders, and answer ShopSmart policy questions."
- No products: "I couldn't find products matching those filters."
- No promotion: "I couldn't find an active offer that applies to this request."
- No order: "I couldn't find that order in your account."
- No policy evidence: "I couldn't find that information in ShopSmart's policy knowledge."
- Auth required: "Please sign in to continue."
- Service error: "That service is temporarily unavailable."

## Edge Cases and Safety Behavior

Invalid numeric filters fail validation rather than being ignored. Unknown categories are unsupported or return no results; they never degrade to loose text matching. Empty search and zero results return the no-product response. Product references not in the user's bounded, structurally validated prior result set cannot be mutated. Cross-user cart/order/conversation identifiers fail closed. Missing promotion capability returns no active offer, never a guessed discount. Missing policy evidence returns the no-policy-evidence response. Provider failure does not erase or fabricate tool results. Malicious retrieved knowledge is untrusted data, never instructions. Mutating requests without authenticated session/CSRF are rejected.

## Out of Scope

No arbitrary SQL/model-driven database access, autonomous checkout/payment, model-selected provider/model, customer-upload-dependent UX, cross-user data, invented promotion rules, mandatory paid provider, Jev, required cloud vector infrastructure, image OCR, or unverified roadmap Days 73-75 content.

## Success Criteria

- The normal assistant experience shows commerce prompts/conversation and no customer upload form.
- Each of the eleven intents has deterministic fixture coverage and correct route behavior.
- Exact price/stock and cart/order state in responses match authoritative service results; no dynamic fact comes from RAG or model-only text.
- Tool and API tests demonstrate zero cross-user cart/order/conversation access and reject unauthorized/stale product references.
- Policy answers cite only actual ShopSmart-owned retrieved sources; unsupported policy questions return the specified no-evidence response.
- Greeting/help and deterministic tool/no-result answers make zero unnecessary provider calls; numeric product constraints are enforced structurally.
- Offline evals measure routing, tool choice/arguments, commerce correctness, policy retrieval/grounding/citations/no-answer, and security regressions.
- A fresh local seed and a repeat seed produce the same seed-owned records; reset removes those records and leaves unrelated developer data intact.
- The realistic dataset supports at least 1,000 active/inactive catalog records where laptop performance permits, and validation covers each supported cart/order scenario and assistant flow.
- Baseline latency is recorded for catalog, assistant, cart, order, and policy paths, with no test making correctness dependent on a paid provider.
- Full frontend/backend quality gates pass without paid provider credentials, and production cookie/CSRF/provider governance behavior is unchanged.

## Key Entities

User, Product (including normalized category), Cart, CartItem, Order, OrderItem, Promotion (if/when authoritative promotion capability exists), ShopKnowledgeSource, KnowledgeVersion, KnowledgeChunk, Conversation, ChatMessage, ConversationProductReference, Citation, EvaluationCase, EvaluationReport, SeedOwnershipMarker.

## Assumptions

Existing product, cart, and order services remain authoritative and are reused. Product prices retain the repository's current money-unit/currency contract; assistant formatting must not reinterpret integer values as another currency. Current code has no promotion/discount service, so no discount can be claimed until one exists. Shop policy RAG must be server/admin-owned and versioned; any retained user-owned ingestion is test/internal only. Deterministic routing and a local provider are sufficient for local operation. The vector index remains derived/rebuildable. No new dependency or service is justified for this change. Seed ownership MUST be implemented using the narrowest existing supported mechanism; if that requires a new schema object, its scope and migration must be reviewed before implementation.
