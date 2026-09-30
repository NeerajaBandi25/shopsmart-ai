# Feature 008 Tasks: AI/RAG and Evals

## Design

- [ ] T001 Create spec, plan, task traceability and AI runbook.
- [ ] T002 Add AI configuration with bounded upload/chunk/context/retry/provider limits.
- [ ] T003 Add migration and SQLAlchemy models for documents, versions, chunks, conversations, and messages.

## Ingestion and Retrieval

- [ ] T004 Implement safe PDF/plain-text extraction, normalization, deterministic overlapping chunking, hashes, metadata, and idempotent versioning.
- [ ] T005 Implement deterministic embedding and provider protocols with failure handling.
- [ ] T006 Implement owner-scoped repositories and thresholded top-k retrieval with deduplication/context budgets.
- [ ] T007 Add ingestion, chunking, embedding, retrieval, malformed/empty/large/retry tests.

## RAG and API

- [ ] T008 Implement bounded context construction and evidence-only answer provider with no-answer behavior.
- [ ] T009 Implement authenticated upload, document, conversation, chat, and citation routes.
- [ ] T010 Add AI telemetry without sensitive content and test logging/metrics controls.
- [ ] T011 Add backend integration and security tests for owner isolation, injection, citations, failure, and history.

## Frontend

- [ ] T012 Add same-origin AI BFF handlers, typed client, and protected assistant UI.
- [ ] T013 Add chat/upload/loading/error/no-answer/citation/history/retry tests.

## Evaluations

- [ ] T014 Add versioned golden dataset and accepted baseline.
- [ ] T015 Implement deterministic evaluator and CLI for retrieval, answer, citation, safety, behavior, system, and regression metrics.
- [ ] T016 Add eval execution and security regression tests; document results and known weaknesses.

## Review and Release

- [ ] T017 Perform AI/RAG, security, performance/cost, and independent code reviews.
- [ ] T018 Fix findings and rerun focused tests/evals.
- [ ] T019 Run full backend/frontend/CI/migration/security/scope validation and inspect diff.
- [ ] T020 Commit `feat(ai): complete Feature 008 RAG and evaluation`, push `feature/008-ai-rag`, and open the requested PR without merging.
