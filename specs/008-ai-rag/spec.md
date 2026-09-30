# Feature Specification: AI/RAG and Reproducible Evaluations

**Feature Branch**: `feature/008-ai-rag`
**Status**: Draft
**Roadmap scope**: The authoritative roadmap names OpenAI integration, PDF loading/chunking, embeddings, FAISS/vector search, RAG retrieval, citations, streaming chat, conversation history, and deployment. It does not prescribe a cloud vector database, Jev, exact model, or Days 73-75 content. This feature therefore provides a deployable local implementation with replaceable provider boundaries and no mandatory paid service.

## User Scenarios and Testing

### User Story 1 - Upload a private knowledge document (P1)
An authenticated user uploads a supported PDF or text document. The system validates ownership, size/type, safely extracts text, normalizes it, creates bounded overlapping chunks with source metadata, and indexes a version. Duplicate content is idempotent; failed indexing is visible and retryable without an infinite loop.

### User Story 2 - Ask a grounded question (P1)
An authenticated user asks a question. The system routes it as a document question, retrieves only that user's indexed chunks, applies a similarity threshold and bounded top-k, builds limited context, and returns an answer only when evidence supports it. Every citation refers to an actual returned chunk; insufficient evidence produces a safe no-answer response.

### User Story 3 - Continue a private conversation (P1)
An authenticated user can create and page through their own conversations and ask follow-ups. History is persisted without copying document contents into every message, bounded before prompt construction, and never visible to another user.

### User Story 4 - Evaluate quality and safety (P1)
An engineer runs a versioned golden dataset offline using deterministic embeddings and a mock provider. The report measures retrieval, answer grounding, citation, safety, behavior, latency, token, cost, and regression metrics and records known weaknesses rather than hiding low scores.

## Data Flow

`USER -> AUTH/USER ISOLATION -> QUERY ROUTING -> RETRIEVAL -> FILTER/RERANK -> CONTEXT CONSTRUCTION -> LLM/PROVIDER -> ANSWER + CITATIONS -> EVALS/TELEMETRY`

## Authoritative Sources of Truth

PostgreSQL is authoritative for users, document ownership/status/version metadata, chunks, conversations, and messages. Stored chunk text is authoritative evidence for citations. The vector index is a derived retrieval structure and may be rebuilt. The authenticated session dependency is authoritative for user identity. The golden dataset and accepted baseline are versioned repository artifacts.

## Functional Requirements

- **FR-001**: Require an authenticated session for document, conversation, and chat operations; every query and repository operation MUST carry the authenticated user ID.
- **FR-002**: Accept only configured PDF/plain-text uploads with safe filenames and a configurable maximum size; reject empty, malformed, unsupported, and oversized input without retaining unsafe content.
- **FR-003**: Normalize extracted text and split it into deterministic bounded chunks with overlap; preserve document ID, version, chunk index, page/source label, and content hash for citations.
- **FR-004**: Make ingestion idempotent by content hash and document owner; support version status, bounded retry state, and explicit failure without uncontrolled background loops.
- **FR-005**: Generate embeddings behind an interface. The default local provider MUST be deterministic and offline-testable; live providers are optional configuration and MUST fail closed without an API key.
- **FR-006**: Retrieve only active chunks whose owner equals the authenticated user, using top-k, a similarity threshold, duplicate suppression, and bounded context size. Authorization MUST occur before ranking or context construction.
- **FR-007**: Route document questions deterministically and avoid sending catalog/cart/order state to the model unless a separately authorized source is explicitly added.
- **FR-008**: Generate grounded answers behind a provider interface. The default provider MUST return a deterministic evidence-based answer for local operation; unsupported questions MUST return a no-answer response.
- **FR-009**: Return citations only from retrieved chunks and include source title/page/chunk metadata. Citation IDs MUST NOT expose private paths or unrelated users' data.
- **FR-010**: Persist conversations/messages with owner constraints and bounded history; provide deletion and pagination behavior.
- **FR-011**: Provide a streaming-compatible chat endpoint or documented non-streaming fallback that handles disconnect, timeout, retrieval failure, malformed provider output, and cancellation without leaked tasks.
- **FR-012**: Record bounded AI metrics for retrieval/model latency, failures, no-answer events, token/cost estimates, and evaluation outcomes without raw prompts, tokens, document contents, cookies, or authorization headers.
- **FR-013**: Include prompt-injection and indirect-document-injection defenses: retrieved text is evidence, never instructions; generated actions/tools are unavailable in this feature; metadata filters are server-controlled.
- **FR-014**: Provide a versioned golden dataset and reproducible evaluator measuring recall@k, relevance/precision, ranking quality, correctness, groundedness, completeness, citation correctness/coverage, unsupported claims, hallucinations, unauthorized retrieval, injection resistance, no-answer behavior, latency, tokens, cost, and regression against an accepted baseline.
- **FR-015**: Preserve existing authentication, commerce, Redis, deployment, and observability contracts; add only focused AI routes, migrations, UI, tests, documentation, and configuration.

## Edge Cases and Safety Behavior

Duplicate upload returns the existing successful version. Re-ingestion creates a new version while old versions remain inactive. Empty/malformed/oversized input fails with a safe error. Embedding failure records a failed status and bounded retry count. Empty, irrelevant, stale, malicious, or unauthorized retrieval always yields no-answer or a retrieval error; it never becomes an ungrounded answer. A follow-up with insufficient bounded history is answered from current evidence or declined. A client disconnect cancels provider work.

## Out of Scope

No Jev dependency, autonomous tools/actions, payments/order decisions, cross-user/shared document search, mandatory OpenAI account, mandatory FAISS deployment, OCR for image-only PDFs, cloud infrastructure provisioning, or exact roadmap content beyond the readable source.

## Success Criteria

- Authenticated ownership tests demonstrate zero cross-user document/chunk/conversation retrieval.
- Deterministic ingestion is repeatable and chunk metadata supports every returned citation.
- Golden evaluation runs offline from a clean checkout and emits a versioned report with baseline comparison and no hidden failures.
- The evaluator reports retrieval recall@k, citation correctness/coverage, groundedness, unsupported-claim rate, injection resistance, no-answer accuracy, latency, tokens, and cost estimate.
- Security tests pass for direct and indirect prompt injection, malicious metadata, unauthorized access, and sensitive-log leakage.
- Existing backend/frontend/CI gates remain intact and the application can run without paid AI credentials.

## Key Entities

User, Document, DocumentVersion, DocumentChunk, Conversation, ChatMessage, RetrievedCitation, EvaluationCase, EvaluationReport.

## Assumptions

The first production deployment uses PostgreSQL and local deterministic providers unless operators configure an external provider. Text extraction supports PDF text streams and plain text; image OCR is a documented limitation. The vector index is derived and rebuildable from PostgreSQL chunks. Jev is not used because the roadmap does not require it and a mandatory orchestration dependency would add failure and cost without an established evaluation benefit.
