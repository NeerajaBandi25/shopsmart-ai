# AI architecture

The router recognizes portfolio categories, compound aliases and budget shorthand. Legacy phones/home/appliances names may retry their mapped portfolio category after an empty result; the retry preserves price and stock constraints and never broadens to the entire catalog. Distinct configurations reduce color-only duplication.

Buying advice derives price, published memory and scalar specifications from the current comparison shortlist. `buying_brief` carries per-product reasons for structured rendering. Advice qualifies missing gaming benchmarks and battery measurements. Cheapest-value explanation is implemented; comprehensive benchmark-based best-performance/best-battery scoring is not.

Cheaper-item follow-ups resolve current shortlist facts before calling CartService. Checkout intent returns a current cart and `/checkout` navigation only for a nonempty cart. PDP questions seed assistant search with the full product name; the command palette carries queries into catalog or assistant.

The effective provider classification is the highest of the declared request and all supplied evidence. Public policy snippets cannot downgrade private questions. Regression tests cover this in `backend/tests/unit/test_ai_gateway.py`.

Commerce intent is routed in `backend/src/services/assistant_router.py`. `CommerceAssistantService` checks conversation ownership, executes catalog/cart/promotion/order services, and returns typed structured data. Follow-up references resolve through stored product IDs and rehydrate current records.

The AI authority boundary is deliberate: live commerce facts come from services, not retrieved prose or provider-generated product objects. Shopping operations can run without an external LLM.

Policy/support questions retrieve active curated knowledge through `assistant_knowledge.py`. User-document retrieval in `ai_retrieval.py` filters owner and ready state; document routes require a separate internal capability and are hidden from the public API schema. The provider receives evidence as untrusted context. Returned evidence IDs determine citations; insufficient evidence produces a no-answer result.

`ai_governance.py` allowlists providers, models and data classifications. Configured external providers accept PUBLIC content; deterministic generation can handle the configured internal classifications. `ai_gateway.py` applies policy-first selection, timeouts, retries and fallback.

Limitations to explain:

- A deterministic parser has bounded language coverage; test the actual intended phrases.
- Conversation context is not unrestricted model memory.
- Embeddings/retrieval have a local implementation; ranking currently scans accessible chunks.
- Provider counters are process-local, and the quota implementation is not a distributed daily budget.
- Provider retention/training policy fields describe required configuration, not a verified contractual guarantee.

Trace a structured product result through `frontend/src/components/assistant/CommerceResults.tsx` to show why an attractive card is still grounded in commerce records.
