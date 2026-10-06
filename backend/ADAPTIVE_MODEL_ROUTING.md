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

The suite exposed a coverage weakness as well as model weaknesses: the ranking case currently expects exact synthetic product-name reproduction from a ranking-only tool call. Keep its failure visible while improving the golden case to measure structured recommendation choice and evidence. Redis was unavailable during the first live run, so that process could not persist benchmark scores for a later process.

## Task-specific gate correction and rerun

The first benchmark version incorrectly used the aggregate model gate when publishing every task score. This meant a model with a failed comparison case also lost its passing search and mission scores. Score publication now gates each task using only objective metrics represented by that task's cases, while the aggregate report retains its full-suite gate. The benchmark was rerun against the same three free models on 2026-10-06 after this change:

| Model | Tool correctness | Mission extraction | Constraints | Grounding | Recommendation | Completion | Mean latency | Tokens in / out | Provider failures | 429s | Task gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apodex/apodex-1.1-mini:free` | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 3,685 ms | 7,517 / 661 | 0 | 0 | search PASS, advice PASS, compare FAIL |
| `cohere/north-mini-code:free` | 0.67 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 6,262 ms | 3,111 / 752 | 0 | 0 | search PASS, advice PASS, compare FAIL |
| `dots-studio/dots-3-note-preview:free` | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 6,315 ms | 6,481 / 846 | 0 | 0 | search PASS, advice PASS, compare FAIL |

All three still fail the aggregate comparison set because none grounded the rank-one synthetic product name in its final comparison synthesis. The important routing result is task-specific: valid search/advice scores survive; PRODUCT_COMPARE receives score zero and cannot rank those candidates. The complete raw report is at `backend/evals/results/adaptive-model-live-v3.json` (local runtime artifact; not committed). Redis remained unavailable, so benchmark scores used request-local fallback state and were not persisted across processes. Do not claim complete model qualification from this three-case subset.

The comparison case was then made more explicit about its required grounded synthesis (name the provided rank-one item and cite its verified specs), without changing thresholds, and run again through the host-network runtime. The latest result is:

| Model | Tool correctness | Mission extraction | Constraints | Grounding | Recommendation | Completion | Mean latency | Tokens in / out | Provider failures | 429s | Task gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apodex/apodex-1.1-mini:free` | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 0.67 | 5,410 ms | 7,601 / 945 | 0 | 0 | search FAIL, advice PASS, compare PASS |
| `cohere/north-mini-code:free` | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.67 | 8,441 ms | 4,127 / 1,019 | 0 | 0 | search PASS, advice FAIL, compare PASS |
| `dots-studio/dots-3-note-preview:free` | 0.67 | 1.00 | 1.00 | 0.00 | 0.00 | 0.33 | 5,837 ms | 5,057 / 864 | 0 | 0 | search FAIL, advice PASS, compare FAIL |

No candidate passed the full three-case aggregate. The per-task gates now preserve useful measured routes for search, advice, and comparison rather than marking every model unusable. Because Redis was still unavailable, cross-process score persistence and live reuse remain unverified. This three-case set is a bounded routing smoke, not a broad estimate of model quality; the complete local output is `backend/evals/results/adaptive-model-live-v4.json` and is excluded from Git.

The final live run added an explicit catalog-grounding instruction to the search case, retaining the same exact-match scoring and unchanged thresholds. Apodex passed the complete three-case suite:

| Model | Tool correctness | Mission extraction | Constraints | Grounding | Recommendation | Completion | Mean latency | Tokens in / out | Provider failures | 429s | Aggregate gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apodex/apodex-1.1-mini:free` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 4,643 ms | 7,639 / 943 | 0 | 0 | PASS (.9923 score) |
| `cohere/north-mini-code:free` | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.67 | 8,466 ms | 4,165 / 974 | 0 | 0 | FAIL: mission extraction, completion |
| `dots-studio/dots-3-note-preview:free` | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 6,997 ms | 6,603 / 941 | 0 | 0 | FAIL: comparison grounding/recommendation, completion |

Apodex passed PRODUCT_SEARCH, PRODUCT_ADVICE, and PRODUCT_COMPARE gates, while its runner-up models remain gated per task. This is evidence for the current three-case routing smoke only; expand the cases before treating these scores as a broad quality estimate. Redis remained unavailable, so benchmark scores could not be published across processes in this run. Full raw output: `backend/evals/results/adaptive-model-live-v5.json` (local, not committed).

## Expanded six-case comparison (2026-10-06)

Dataset v2 doubles the controlled cases to six: two catalog searches (including phone price conversion and stock filtering), two mission extractions (including student portability), and two ranked recommendations (including a best-value/lower-cost trade-off). Mission scoring now evaluates requested soft fields as well as desired-use labels. The quality gates remain unchanged at 1.0 for objective checks and zero provider failures/rate limits.

| Model | Tool | Mission | Constraints | Grounding | Recommendation | Completion | Mean latency | Tokens in / out | Failures / 429s | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `apodex/apodex-1.1-mini:free` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 970 ms | 0 / 0 | 6 / 6 | FAIL: HTTP 429 on every case |
| `cohere/north-mini-code:free` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 5,892 ms | 7,922 / 2,121 | 0 / 0 | PASS (.9902 score) |
| `dots-studio/dots-3-note-preview:free` | 1.00 | 1.00 | 1.00 | 0.50 | 0.00 | 0.67 | 7,947 ms | 12,696 / 1,547 | 0 / 0 | FAIL: compare synthesis |

This run used ShopSmart's provider adapter and captured upstream HTTP 429 for all six Apodex cases; it did not infer a connectivity failure. Cohere passed all six synthetic cases, while Dots passed search/advice and failed both comparison syntheses. Redis was unavailable, so the model scores were not reusable across processes. This is a stronger but still bounded evaluation, not a general quality guarantee. Raw local report: `backend/evals/results/adaptive-model-live-v6.json` (excluded from Git).
