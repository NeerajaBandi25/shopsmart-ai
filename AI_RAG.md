# AI/RAG Runbook

Feature 008 adds an authenticated document assistant. PostgreSQL stores document ownership, versions, chunks, conversations, and messages. The vector representation is derived from persisted chunks and can be rebuilt; it is never an authorization source.

The default embedding and answer providers are deterministic and offline. They make local development and evaluation reproducible. A production provider can implement the same interfaces, but must preserve owner-filtered retrieval, bounded context, evidence-only citations, no-answer behavior, and secret-free telemetry. Jev is intentionally not used: it is not required by the readable roadmap and would add an avoidable single-point failure.

Run the evaluator with `python -m src.evals.runner --dataset evals/datasets/golden_v1.json --baseline evals/baselines/v1.json`. It executes deterministic embedding retrieval and the local evidence-only provider over controlled fixtures, then exits non-zero when the accepted baseline is not met. The deterministic baseline is a safety and regression contract, not a claim about live LLM quality.

Known limitations: image-only PDF OCR is not included; the local vector index is linear and intended for bounded MVP data; live provider quality/cost must be measured separately; streamed transport is represented by a bounded service contract and can be promoted to SSE without changing retrieval or citation rules.
