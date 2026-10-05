# ShopSmart AI assistant flow

## WHAT

The assistant can use a real language model to interpret public product and policy requests and select from an explicit set of ShopSmart tools. Python services remain the source of truth for catalog data, stock, promotion eligibility, cart totals, and orders. The existing deterministic assistant remains the offline/test path and the safe fallback.

## WHY

Language models are useful for understanding varied wording and explaining returned facts. They are not trusted to create prices, stock, discount, ownership, or order facts. Each important fact comes from an authenticated service call, then the response is returned to the existing structured storefront UI.

## REQUEST FLOW

1. `frontend/src/app/assistant/page.tsx` sends the current question and conversation ID to the same-origin `/api/ai/chat` route with the session cookie and CSRF token.
2. `frontend/src/app/api/ai/chat/route.ts` and `_ai-proxy.ts` forward the request to FastAPI `/api/v1/ai/chat`.
3. `backend/src/api/v1/ai_routes.py` requires the signed-in user and CSRF token, then calls `CommerceAssistantService`.
4. If `AI_PROVIDER` selects a configured external provider, route extraction happens locally. The provider receives typed route fields, reviewed product/policy vocabulary, rehydrated public product context, allowlisted tool schemas, and system policy; raw user messages and conversation text are not sent. Otherwise the deterministic route/service path handles the request.
5. `ProviderGateway` selects an eligible provider. Function-call arguments are validated by `assistant_tools.py`; tools use existing catalog, cart, order, and knowledge services with the authenticated user ID.
6. Tool results are returned to the model as structured function results. The bounded loop permits at most five tool calls per assistant request. The user-facing factual response is composed from verified service results, not free-form model prose, and saved with structured result data in the owner-scoped conversation.

## LLM PROVIDER

`backend/src/services/ai_gateway.py` uses `httpx` directly. OpenRouter and Groq use OpenAI-compatible chat-completion function calls; Gemini uses its `generateContent` function declarations. Optional OpenAI-compatible endpoint support uses `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`. No key is required for the deterministic path.

Set one provider explicitly in a local environment, for example `AI_PROVIDER=openai_compatible`, and supply its server-side credential. `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, and `GEMINI_API_KEY` must never go to browser code. If provider calls fail, the assistant marks the response as degraded and runs the deterministic path when no mutation has already occurred.

The gateway classifies normal product/policy calls as PUBLIC. Cart, order, coupon, checkout, and eligibility calls stay on the local deterministic path unless `AI_EXTERNAL_PRIVATE_DATA_ENABLED=true` is explicitly configured. Enabling it sends private tool results to the selected provider and requires a deployment decision about provider data handling.

## TOOL CALL LOOP

The allowlist in `backend/src/services/assistant_tools.py` contains `search_products`, `get_product_details`, `compare_products`, `get_promotions`, `evaluate_promotion`, `apply_promotion`, `remove_promotion`, `get_cart`, `add_to_cart`, `remove_from_cart`, `get_orders`, `get_order_status`, and `retrieve_policy_knowledge`. Tool arguments use Pydantic models with unknown fields rejected, bounded lengths/counts, UUID validation, category/sort allowlists, and INR minor-unit ranges. RAG is omitted from external tool schemas by default; set `AI_EXTERNAL_PUBLIC_KNOWLEDGE_SOURCE_KEYS` to an explicit comma-separated list of reviewed source keys before the external model can retrieve those sources.

No SQL, arbitrary HTTP, filesystem, or repository tool exists. Product details, comparisons, and cart mutations rehydrate product IDs from the current conversation's authorized search state. A cart removal must reference a product already in the authenticated user's cart. Only one cart/promotion mutation is allowed per assistant request, and provider retries never replay a completed tool mutation.

## AUTHORIZATION

FastAPI derives identity from the authenticated session; no model-supplied user ID is accepted. `ConversationRepository.get_owned` checks conversation ownership. `OrderService.get_user_order` and `get_user_orders` scope reads to the authenticated user. Cart and promotion services always receive that same server-derived identity. An arbitrary order ID returns the same unavailable result as a foreign or missing order.

## GROUNDING

The model receives tool results as function-result messages, never concatenated into system instructions. Its final free-form text is not trusted or shown as factual output. Product cards, totals, promotion results, and cart details in `result_data` remain service output; the backend composes concise replies from those results. Policy replies quote a bounded excerpt from an explicitly approved source and attach its exact citation marker. Missing evidence is answered as unavailable. If the model skips tools, the backend uses the deterministic assistant path.

## RAG

`KnowledgeRetrievalService` searches active server-published ShopSmart knowledge only. The external provider path additionally filters retrieval by the explicit source-key allowlist above; local seeded/evaluation knowledge is not exposed by default. It is not used for price, stock, promotions, cart, or orders. Retrieved passages are marked untrusted in tool results and cited by source marker; malicious instructions inside a passage must not change the system policy. The current local embedder is deterministic token-hash embedding, not a hosted embedding model.

Obvious account/payment identifiers in otherwise public-looking queries (such as email addresses, phone-like values, passwords, card details, and personal order/account references) bypass the external provider and stay on the local path.

## MULTI-TURN

The database retains conversation history for the signed-in user, but that free-form text is never sent to an external provider. The provider receives a server-generated route summary with terms drawn from a small reviewed vocabulary, and product IDs are reloaded from the active catalog. Price, availability, and specifications are never trusted from old model text. Private cart/order/promotion tool results are sent only with the explicit private-data opt-in.

## FAILURE HANDLING

Provider timeouts and transport failures use bounded retries; only provider requests are retried. Retryable HTTP 429 and 5xx responses may try another eligible provider. Invalid schemas, unknown tools, failed authorization, and provider policy rejections fail closed. After a cart/promotion mutation, the service does not rerun the tool or switch to a second execution path; it returns a server-built confirmation from the committed service result. Current provider responses are buffered JSON. There is no SSE/token streaming; buffering ensures the UI receives final structured results only after tool execution and persistence.

## OBSERVABILITY

Logs include request correlation, provider/model, latency, input/output token counts, tool names/status, fallback, and configured estimated cost. They exclude prompts, credentials, cookies, and full tool payloads. The authenticated `/api/v1/ai/usage` endpoint summarizes the latest 2,000 messages for the current owner. Cost is `null` until `AI_MODEL_PRICING_JSON` provides model-specific per-million input/output rates. Message token counts and usage metadata are stored with the conversation.

## HOW TO TEST

- Unit tests validate tool schemas, provider response normalization, gateway policy, and fallback behavior.
- Contract tests exercise the authenticated assistant API and owner scoping.
- Live provider checks are opt-in with `RUN_LIVE_AI_TESTS=true`, require a non-production provider key, and must never run as ordinary CI tests.
- `AI_PROVIDER=deterministic` runs offline and does not prove external-provider behavior.

## HOW TO DEBUG

Check the active backend process's `AI_PROVIDER` and credential presence without printing credential values. Look for `LLM_REQUEST_STARTED`, `LLM_RESPONSE_RECEIVED`, `TOOL_REQUESTED`, `TOOL_STARTED`, `TOOL_COMPLETED`, `TOOL_FAILED`, `AI_USAGE_RECORDED`, and `ASSISTANT_RESPONSE_COMPLETED`. A response with `degraded_mode=true` used deterministic fallback. Inspect owner-scoped `/api/v1/ai/usage`; configure a model pricing map only from the provider's current pricing source.

## INTERVIEW EXPLANATION

“The LLM chooses from typed tools, but every commerce fact and mutation is handled by an authenticated ShopSmart service. The assistant validates arguments and ownership, limits tool loops, rechecks product references, returns tool data for grounded explanation, cites retrieved policy evidence, and records bounded usage. The deterministic implementation remains an explicit offline fallback rather than pretending to be a language model.”
