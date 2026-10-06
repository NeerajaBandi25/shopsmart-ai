# Adaptive OpenRouter model routing

ShopSmart defaults to `AI_MODEL_ROUTING_MODE=ADAPTIVE_FREE` when using OpenRouter. Before a commerce-agent loop begins, it reads OpenRouter's model catalog, keeps zero-price text models that advertise tool support, checks the streaming capability when supplied, and scores each model for the current assistant intent. The selected model is pinned for all turns in that request. If OpenRouter's `openrouter/free` fallback returns a concrete model ID, ShopSmart pins that reported ID for the remaining turns.

The rank is deterministic: task-specific eval score (50%), recent reliability (25%), 429 avoidance (15%), and latency (10%). A zero task score means the model failed the benchmark's objective quality gate and is excluded from ranked candidates. If Redis becomes unavailable during a request, routing switches to local state after one failed probe for that request; the next request probes Redis again. Redis stores a three-minute catalog cache and expiring model keys:

| Key | Value | TTL |
| --- | --- | --- |
| `ai:model:<id>:health` | healthy/degraded | 5 minutes |
| `ai:model:<id>:latency` | latest successful request latency in milliseconds | 1 hour |
| `ai:model:<id>:429_rate` | rolling 429 fraction | 15 minutes |
| `ai:model:<id>:failure_rate` | rolling failure fraction | 15 minutes |
| `ai:model:<id>:circuit_state` | closed/half_open/open | 1 minute |
| `ai:model:<id>:eval_score:<task>` | latest controlled task score | 1 day |

The Redis counter window is shared across workers. When Redis is unconfigured or unavailable, the same signals use a bounded process-local fallback; model selection remains deterministic, while health history lasts only for the process lifetime.

If a pinned model fails before or during a read-only tool loop, ShopSmart discards the old transcript and restarts from the original bounded request with the next ranked candidate. Mutating tool actions are never replayed. After ranked candidates, `openrouter/free` is the emergency free route; if it fails, ShopSmart returns to deterministic catalog behavior. Authentication rejection does not fan out across models.

`FIXED` mode requires a concrete `AI_FIXED_MODEL` and is intended for reproducible debugging. `BENCHMARK` mode is reserved from customer traffic. Run the controlled model comparison from `backend/`:

```powershell
python -m src.evals.adaptive_model_eval --output evals/results/adaptive-model-latest.json
```

By default the benchmark compares at most the three top-ranked eligible free models for `PRODUCT_ADVICE`; `--limit` can set a bound from one to ten. Optionally pass a comma-separated `--models` list; every ID must still be discovered as a free tool-capable model, and the set cannot exceed the configured limit. The benchmark uses synthetic catalog facts and read-only tool calls, measures tool correctness, mission extraction, constraint accuracy, grounded synthesis, recommendation choice, latency, tokens, rate limits, provider failures, and completion reliability, then stores task scores in Redis for later routing. It does not execute cart/order mutations or write user data. CI exposes this as a manual workflow input, off by default, and stores the report as a short-lived artifact.

The streaming adapter pins the same model, includes provider usage when available, and falls back to a buffered call on that same model when the provider rejects SSE. OpenRouter's catalog does not expose a stable per-model streaming capability field; when the field is absent, candidate eligibility relies on the chat-completions API and the adapter's same-model buffered fallback. Therefore browser SSE compatibility is guaranteed by ShopSmart's response adapter, while upstream token streaming remains best-effort until a candidate is exercised. ShopSmart streams only tool progress and verified output to the browser.

## Live comparison snapshot (2026-10-06)

A credentialed benchmark ran through the ShopSmart backend against three currently eligible free models and three synthetic cases. No case mutates commerce state. The strict quality gate requires 1.0 for each objective metric in this deliberately small initial suite; all candidates failed, so these measurements are diagnostic and are not evidence that a candidate is production-qualified.

| Model | Tool correctness | Mission extraction | Constraint accuracy | Grounding | Recommendation | Completion | Mean latency | Tokens in / out | Provider failures | 429s | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apodex/apodex-1.1-mini:free` | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 3,606 ms | 7,517 / 627 | 0 | 0 | FAIL |
| `cohere/north-mini-code:free` | 0.67 | 0.00 | 1.00 | 0.50 | 0.00 | 0.33 | 7,772 ms | 3,111 / 725 | 0 | 0 | FAIL |
| `dots-studio/dots-3-note-preview:free` | 0.67 | 0.00 | 1.00 | 0.50 | 0.00 | 0.33 | 15,405 ms | 5,304 / 784 | 1 timeout | 0 | FAIL |

The suite exposed a coverage weakness as well as model weaknesses: the ranking case currently expects exact synthetic product-name reproduction from a ranking-only tool call. Keep its failure visible while improving the golden case to measure structured recommendation choice and evidence. The router excludes models whose persisted task score is zero; only a quality-gated score is fed back into routing. Redis was unavailable during this run, so this process used request-local health state and could not persist benchmark scores for a later process.
