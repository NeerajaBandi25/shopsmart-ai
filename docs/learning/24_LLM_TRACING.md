# 24. LLM tracing

## What and why

Operational traces explain which route, model, tools, guardrails and fallbacks handled an assistant request without retaining sensitive conversation content.

## Flow and files

Request and trace IDs follow the AI request through intent extraction, provider calls, typed tool execution, retrieval, ranking, synthesis and output checks. Structured records include provider/model, prompt and guardrail versions, latency, input/output tokens when reported, tool names/durations, retrieval source IDs, Redis cache status, fallback and error category. The existing request logger redacts secret-like values.

## Privacy and failure modes

Traces do not include API keys, cookies, authorization headers, payment data or raw customer prompt text. Providers can omit token usage, and model pricing can be unset; those measures must remain null/unknown, not guessed. Deterministic requests report their route without pretending a network call occurred.

## How to debug

Correlate `request_id` across the HTTP request and structured AI events. Confirm that the rendered log allowlist retains trace fields and that failure records identify an error category without exposing provider response bodies.

## Interview explanation

“We preserve request correlation, model cost signals, tool outcomes and cache/fallback decisions while deliberately excluding raw sensitive content.”
