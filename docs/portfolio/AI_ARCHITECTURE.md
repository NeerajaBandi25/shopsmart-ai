# ShopSmart AI architecture

## Runtime

The Shopping Assistant flows from the Next.js page through the same-origin AI BFF to the authenticated FastAPI `/api/v1/ai/chat` endpoint. `CommerceAssistantService` selects an external-provider tool loop only when `AI_PROVIDER` explicitly names a configured provider; otherwise it runs the deterministic offline path.

`ProviderGateway` supports OpenRouter, Groq, Gemini, and a generic OpenAI-compatible API through server-side `httpx` calls. The gateway owns provider selection, data-classification policy, timeout/retry behavior, fallback, and provider/model logging. `OPENAI_BASE_URL` supports an OpenAI-compatible endpoint; it is not a provider name by itself.

## Tool authority

The external model receives JSON schemas generated from strict Pydantic tool-argument models. The allowlist is in `backend/src/services/assistant_tools.py`; it calls the existing catalog, cart, promotion, order, and knowledge services. The server supplies the authenticated user identity. Product IDs are limited to conversation search results and reloaded from the active catalog before use. Order reads are owner-scoped. Arbitrary SQL, HTTP, filesystem, and code execution are not available.

Tool results are sent back to the model using provider-native function-result messages, with a five-call request limit. Raw user and history text is not sent; the external request contains a locally built route summary and reviewed intent vocabulary. Structured `result_data` remains authoritative for product cards, price, stock, comparisons, promotion evaluation, and cart totals. The backend composes the user-facing factual response from tool results instead of displaying free-form model claims. Private account/cart/order calls stay local unless `AI_EXTERNAL_PRIVATE_DATA_ENABLED=true`; configuring that flag deliberately permits those private results to be sent to the selected provider.

## Grounding, history, and RAG

Free-form conversation history is stored for the signed-in user but is never sent to an external provider. The provider receives a server-generated route summary plus rehydrated public product context. Product references in context are IDs only and are revalidated from the current database. Private cart/order/promotion tool results are sent only when the explicit private-data opt-in is enabled.

Policy/support RAG searches active server-owned knowledge. External retrieval is disabled unless `AI_EXTERNAL_PUBLIC_KNOWLEDGE_SOURCE_KEYS` explicitly allowlists reviewed source keys; locally seeded synthetic evaluation sources are not exposed by default. It is not a source for price, stock, promotions, carts, or order status. Retrieved content is passed as untrusted function-result data. Policy answers require citation markers that resolve to retrieved sources; absent or uncited evidence returns a no-answer response. The current embedding implementation is deterministic token hashing with local cosine ranking. Obvious PII/payment identifiers in a shopping request remain on the local path.

## Failure and observability

Provider timeouts, rate limits, and server failures get bounded provider-only retries and eligible-provider fallback. Tool mutations are not retried; at most one cart/promotion mutation may run in an assistant request, and the final confirmation is created from ShopSmart's mutation result. Provider failures without mutation use the deterministic path and set `degraded_mode`.

Structured logs include request correlation, provider/model, classification, latency, fallback, token usage, tool names/status, and configured cost estimate. They exclude prompts and credentials. Per-message usage is stored with the conversation, and `/api/v1/ai/usage` provides a user-scoped aggregate over the latest 2,000 messages. Cost remains unavailable until `AI_MODEL_PRICING_JSON` is configured with current pricing metadata.

The assistant UI calls the same-origin `/api/ai/chat/stream` BFF, which forwards FastAPI SSE without buffering. OpenAI-compatible gateways use native provider streaming to assemble a complete tool turn; Gemini or any provider without a streaming adapter uses a buffered call under the same contract. The backend publishes safe tool status and only chunks the verified server-built answer after authoritative tools finish. It does not expose partial tool arguments or model reasoning. The frontend appends the structured `assistant.completed` result once, so streamed text never becomes a source of commerce facts.

## Current constraints

- `AI_PROVIDER` defaults to `deterministic`; set it to `openai_compatible`, `openrouter`, `groq`, or `gemini` for external calls.
- External provider policy allows PUBLIC data by default. Private cart/order/promotion workflows use local deterministic orchestration unless explicitly opted in.
- The deterministic tool fallback handles common fixed intent patterns; it does not provide general LLM reasoning.
- Provider/model counters are process-local, while message usage is persisted. No provider billing API or exact cost reconciliation is implemented.
- External provider quality and latency require opt-in tests using a non-production key; network access is not part of ordinary CI.

For the learner-oriented request trace and debugging steps, see [`docs/learning/08_AI_ASSISTANT_FLOW.md`](../learning/08_AI_ASSISTANT_FLOW.md).
