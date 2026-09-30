# Implementation Plan: AI/RAG and Reproducible Evaluations

**Branch**: `feature/008-ai-rag`  
**Spec**: [spec.md](./spec.md)

## Architecture

Browser -> Next.js same-origin BFF -> FastAPI AI routes -> authenticated session dependency -> AI service -> repositories -> PostgreSQL. The AI service calls a deterministic local embedding provider and grounded answer provider through protocols. A derived in-process vector search implementation ranks persisted chunks; it can later be replaced by FAISS without changing route/service contracts. Telemetry uses the existing bounded metrics and structured logging allowlist.

Pipeline: upload -> validation -> extraction -> normalization -> deterministic chunking -> document/version/chunk persistence -> embedding -> retrieval with owner filter -> threshold/deduplication/context budget -> provider -> answer/citations -> message persistence -> metrics.

## Design Decisions

1. Use PostgreSQL as the source of truth and a rebuildable derived index, avoiding new infrastructure.
2. Use SHA-256 token-feature embeddings for deterministic local retrieval. The provider protocol allows OpenAI embeddings later; no key is required for tests or local startup.
3. Use a conservative evidence-based local answer provider. It quotes/summarizes retrieved evidence and refuses unsupported questions; prompt-injection text is treated as untrusted data.
4. Use dependency-injected repositories/services. Routes contain HTTP concerns only.
5. Use explicit `owner_id` predicates on every document, chunk, conversation, and message read/write. Never accept owner IDs or filters from clients.
6. Implement a bounded, non-background ingestion path first. Retry is explicit and capped in stored version state.
7. Keep chat history bounded by message count and character budget. Store evidence references in message metadata rather than duplicating document text.
8. Provide JSON chat responses and an SSE-compatible event helper. The default endpoint remains deterministic and testable; disconnect handling is covered at the service boundary.

## Data Model and Migration

Add documents, document_versions, document_chunks, conversations, chat_messages, and embedding metadata with foreign keys, indexes, owner constraints, status/retry fields, content hashes, source/page/chunk metadata, and timestamps. Register models in migration metadata and create a single Alembic revision after migration 006.

## Backend Modules

- `src/models/ai.py`: entities and status enums.
- `src/schemas/ai.py`: upload, chat, citation, conversation, and evaluation contracts.
- `src/repositories/ai_repository.py`: owner-scoped persistence.
- `src/services/ai_ingestion.py`: validation, extraction, normalization, chunking, bounded retries.
- `src/services/ai_provider.py`: embedding and answer protocols plus deterministic providers.
- `src/services/ai_retrieval.py`: similarity, threshold, ranking, deduplication, context budget.
- `src/services/ai_chat.py`: route, evidence, context, provider, citations, persistence, safe fallback.
- `src/api/v1/ai_routes.py`: authenticated upload, documents, conversations, chat endpoints.
- `src/core/observability.py`: bounded AI metrics/events only.

## Frontend Modules

Add a protected assistant page and same-origin BFF handlers for documents, conversations, and chat. Add typed API client and a focused chat component with upload, loading, empty, citation, error, retry, and no-answer states. Do not expose backend URLs or provider credentials.

## Evaluations

Store `backend/evals/datasets/golden_v1.json` with cases covering retrieval, multi-document, irrelevant/insufficient/ambiguous, authorization, citations, follow-up, injection, empty retrieval, long context, and provider failure. Add `backend/src/evals/runner.py` and `backend/tests/evals/test_golden_eval.py`. Metrics are computed deterministically from expected chunk IDs, expected answer facts, citation IDs, authorization violations, and bounded timing/token counters. `backend/evals/baselines/v1.json` records the accepted baseline and thresholds. A CLI writes JSON reports outside the repository by default.

## Security and Quality Gates

Tests cover upload validation, malformed/empty/large input, idempotency, versioning, chunking, failed embeddings/retry cap, owner isolation, injection resistance, citation integrity, no-answer, history bounds, provider failure, disconnect-safe cancellation, frontend states, and eval regression. Run Ruff, pytest, pip-audit, frontend Jest/lint/build/format checks, migration validation, diff/secret/generated-artifact checks, and Docker Compose smoke where available.

## Non-Goals and Risks

OCR, paid-model quality claims, autonomous tools, Jev, cloud vector infrastructure, and production provisioning remain out of scope. The deterministic provider is a quality harness and safe local fallback, not a substitute for measuring a selected production LLM. The README and runbook must state this limitation.
