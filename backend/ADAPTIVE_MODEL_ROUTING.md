# Adaptive OpenRouter model routing

ShopSmart defaults to `AI_MODEL_ROUTING_MODE=ADAPTIVE_FREE` when using OpenRouter. Before a commerce-agent loop begins, it reads OpenRouter's model catalog, keeps zero-price text models that advertise tool support, checks the streaming capability when supplied, and scores each model for the current assistant intent. The selected model is pinned for all turns in that request. If OpenRouter's `openrouter/free` fallback returns a concrete model ID, ShopSmart pins that reported ID for the remaining turns.

The rank is deterministic: task-specific eval score (50%), recent reliability (25%), 429 avoidance (15%), and latency (10%). Redis stores a three-minute catalog cache and expiring model keys:

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

The streaming adapter pins the same model, includes provider usage when available, and falls back to a buffered call on that same model when the provider rejects SSE. ShopSmart streams only tool progress and verified output to the browser.
