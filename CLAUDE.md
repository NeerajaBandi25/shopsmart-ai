# ShopSmart AI — Claude Code Project Instructions

## 1. Project mission

ShopSmart AI is one coherent production-style portfolio project and one repository.

The product combines:
- E-commerce: authentication, products, cart, checkout, orders, order history.
- AI assistant: document/PDF upload, ingestion, chunking, embeddings, vector retrieval, grounded answers, source citations, chat/session history.
- Production engineering: PostgreSQL, Redis, FastAPI, Next.js, Docker, CI/CD, AWS deployment, observability, testing and security.

Do not split this into two unrelated portfolio repositories. The roadmap's ShopSmart and DocuAsk work should be integrated into the same product/codebase unless the user explicitly changes that decision.

Primary goal:
Build an interview-defensible, production-oriented system while learning the concepts behind every implementation.

## 2. Source-of-truth roadmap

The uploaded 75-Day Full-Stack AI Engineer Roadmap is the learning plan for this repository.

Its daily rhythm is:
- 00:00–00:45 — theory/concepts
- 00:45–01:30 — hands-on implementation
- end of day — Git commit + interview question/note
- every 7th day is a rest/review day

The roadmap progresses through:
1. SQL/PostgreSQL — ShopSmart database
2. Python — service layer
3. FastAPI + Docker — REST API
4. Next.js + full-stack integration + CI/CD + AWS
5. AI/RAG — integrated document assistant
6. Interview preparation — DSA, system design and behavioral stories

The roadmap explicitly covers database integrity and performance, async Python, repository/service separation, API design, JWT auth, testing, Docker Compose, Redis, Next.js BFF/auth/state/performance, observability, GitHub Actions, AWS SQS/ECS/RDS/Vercel/CloudWatch, RAG, vector search, streaming chat, conversation history, and system design.

Relevant source details:
- SQL phase builds users, products, orders and order_items, then indexes, advanced queries, transactions, locking, window functions, PostgreSQL JSONB/triggers/materialized views, Alembic migrations, and a final ShopSmart schema/integration check.
- Python phase emphasizes type hints, Pydantic validation, async/await, asyncpg pooling, parameterized queries, pytest/coverage, repository/service separation, custom exceptions and structured JSON logging.
- FastAPI phase adds dependencies, middleware, async DB access, JWT authentication, API versioning, cursor pagination, idempotency, global error handling, tests and Docker.
- Full-stack phase adds Compose, Redis caching, Next.js BFF, auth/session integration, React performance, Zustand, React Query, observability, CI/CD and AWS.
- AI/RAG phase covers OpenAI integration, PDF loading/chunking, embeddings, FAISS/vector search, RAG retrieval, citations, streaming chat UI, conversation history and deployment.
- Interview phase covers DSA, e-commerce system design, RAG system design and STAR stories.

### Important roadmap-source limitation

The supplied PDF is titled 75-Day, but the readable source content ends partway through the Day 72 material on page 60. Do not invent exact Day 73–75 source content. Treat those days as unspecified until the user provides the missing material or explicitly defines them.

## 3. Current architecture direction

Preferred high-level architecture:

Browser
  -> Next.js frontend/BFF
  -> FastAPI backend
  -> PostgreSQL
  -> Redis

AI path:
Next.js chat/document UI
  -> Next.js BFF
  -> FastAPI AI service
  -> document storage
  -> ingestion/chunking
  -> embeddings
  -> vector store
  -> retrieval
  -> LLM
  -> grounded answer + source citations
  -> streaming response to UI

Production path:
GitHub
  -> CI
  -> tests/type checks/build
  -> container image
  -> deployment
  -> health checks
  -> logs/metrics/error monitoring

Event path when introduced:
order placed
  -> event/message
  -> SQS
  -> consumer/email or downstream work

Keep component boundaries explicit. Do not collapse DB access, business logic, HTTP concerns and AI orchestration into one large module.

## 4. Repository conventions

Prefer a single repository with clear top-level separation, for example:

frontend/
backend/
infra/
docs/
tests/
scripts/

Backend should preserve the roadmap's separation of:
- API/routes
- services/business logic
- repositories/data access
- models/schemas
- core/configuration/database/auth/logging/exceptions

Frontend should separate:
- app/pages/routes
- UI components
- client/server data access
- state
- validation/types
- API/BFF handlers

Do not create unnecessary microservices. Extract a service only when the architecture or deployment boundary genuinely requires it.

## 5. Daily-development protocol

When the user says a specific Day N is being studied/built:

1. Identify exactly what Day N is teaching/building.
2. Inspect the existing repository before changing code.
3. Connect the day's work to the previous day's implementation.
4. Do not pull future-day features into today's implementation unless required to keep the application runnable.
5. Prefer the smallest production-quality increment that demonstrates the day's concept.
6. Implement with tests.
7. Run the relevant tests/type checks/lint/build checks.
8. Reproduce and fix failures rather than hiding them.
9. Review the diff and remove accidental/generated noise.
10. Make a clean Git commit matching the day's intent.
11. End with the day's interview question/engineering takeaway.

When the user asks for a teaching day, explain the reason behind the implementation before generating large amounts of code.

## 6. Claude Code behavior

Act as an engineering partner, not a blind code generator.

Before modifying code:
- inspect existing files and architecture;
- search for existing implementations;
- reuse stable project conventions;
- avoid duplicate utilities/services;
- state assumptions that affect architecture.

Never:
- invent APIs, files or project behavior without checking;
- silently rewrite unrelated code;
- add dependencies without a reason;
- change architecture merely because a different pattern is fashionable;
- claim tests passed when they were not run;
- claim a feature is production-ready without evidence.

For substantial changes, show the intended change first when practical, then implement.

## 7. Testing and quality gates

Testing is part of implementation, not a final cleanup task.

Backend:
- unit tests for business logic
- repository tests where useful
- API integration tests for important endpoints
- authentication/authorization tests
- validation/error-path tests
- concurrency/transaction tests for checkout-critical behavior

Frontend:
- component behavior tests where valuable
- API/BFF contract tests
- critical user-flow tests

AI/RAG:
- retrieval tests
- citation/source attribution checks
- groundedness/fallback behavior checks
- ingestion/chunking tests
- deterministic tests using controlled fixtures
- avoid using a live paid model for every automated test

Quality target:
Start from the roadmap's 80%+ / 90%+ coverage goals where applicable, but prioritize meaningful coverage over gaming the number.

Always test:
- success path
- validation failure
- missing resource
- auth failure
- permission failure
- dependency failure
- relevant concurrency/idempotency behavior

## 8. Security rules

Never commit:
- API keys
- database passwords
- JWT signing secrets
- AWS credentials
- OAuth tokens
- private certificates
- real user data

Use environment variables or a proper secrets mechanism.

The roadmap contains teaching examples with hard-coded secrets/passwords. Those examples are learning aids, not production rules. Convert them to configuration/secrets before committing production code.

For web authentication:
- prefer secure, httpOnly cookies for browser-visible sessions/tokens;
- protect against CSRF where cookie-based auth requires it;
- do not expose privileged server-side secrets to the browser;
- validate authorization on the backend.

Use parameterized database queries and never interpolate user input into SQL.

Validate uploads:
- allowed file types
- maximum size
- safe filenames/object keys
- authorization
- malware/security considerations appropriate to the deployment

## 9. Database rules

PostgreSQL is the system of record.

Use:
- foreign keys and constraints
- appropriate indexes
- transactions for multi-step business operations
- row locking or an intentional concurrency strategy for stock-sensitive checkout
- migrations for schema changes

Do not manually mutate production schema as an ad-hoc fix.

Measure important queries with EXPLAIN/EXPLAIN ANALYZE when performance is relevant.

Treat checkout as a correctness-critical workflow:
payment/order state and inventory changes must not leave inconsistent partial state.

Idempotency is mandatory for retriable checkout/payment-style operations.

## 10. FastAPI rules

Use:
- typed request/response models
- dependency injection for cross-cutting concerns
- async DB access where appropriate
- explicit API versioning
- consistent error envelopes
- health/readiness checks
- structured logging

Keep HTTP concerns out of domain/service logic.

Do not return internal stack traces or raw exceptions to users.

## 11. Next.js rules

Use the Next.js BFF direction from the roadmap where applicable:

Browser
  -> Next.js server route/BFF
  -> FastAPI

Prefer server-side handling of privileged auth tokens and backend URLs.

Use React performance techniques only where measured/justified:
- memoization
- stable callbacks
- virtualization for large lists
- code splitting

Use Zustand for appropriate client state and React Query for server-state caching/fetching when those are part of the chosen stack.

Avoid putting server state into global client state without a reason.

## 12. Redis rules

Redis is for performance/supporting workloads, not the primary source of truth.

Use it for:
- cacheable product queries
- rate limiting
- other deliberately short-lived coordination/data

Every cache needs:
- key design
- TTL/invalidation strategy
- miss behavior
- failure behavior when Redis is unavailable

The application must remain correct when the cache is empty or temporarily unavailable.

## 13. AI/RAG rules

AI features must be grounded in retrieved project data/documents.

The assistant should:
- retrieve relevant chunks;
- pass only justified context to the model;
- return source/citation metadata;
- clearly say when the answer is not supported by the retrieved document;
- avoid fabricating facts.

RAG pipeline:
ingest -> load -> clean -> chunk -> embed -> store -> retrieve -> rerank when justified -> generate -> cite

Chunking must be tested rather than blindly accepting a fixed number.

For expensive/live model calls:
- abstract the model provider;
- keep temperature/settings deterministic where practical;
- centralize model configuration;
- cache safe/repeatable work;
- support a local/mock provider for tests.

Do not make the repository's entire test suite depend on paid external APIs.

## 14. Observability

Production code should provide:
- structured logs
- request IDs/correlation IDs where useful
- health/readiness endpoints
- error monitoring
- latency/error-rate metrics
- useful business/AI metrics

When debugging:
failure
-> reproduce
-> inspect logs/trace
-> isolate root cause
-> fix
-> add regression test
-> verify

Never simply suppress the error.

## 15. Docker and deployment

Containers should:
- use small trusted base images where practical;
- avoid running the application as root;
- keep dependency installation cache-friendly;
- use environment-driven configuration;
- have deterministic startup commands;
- include health checks where appropriate.

Docker Compose is for local multi-service development.

Production deployment must separate secrets/config from images.

Do not assume a specific cloud free-tier price or quota is permanent. Verify current AWS pricing/limits before spending or making a cost claim.

## 16. CI/CD rules

Every meaningful change should be able to pass:
- backend tests
- frontend tests/build
- formatting/lint/type checks appropriate to the stack
- migration validation where relevant

Pull requests should fail fast on broken quality gates.

Deployment should only happen from a known-good commit.

## 17. AI coding tool usage

Claude Code is an accelerator, not the source of truth.

Before accepting generated code:
- understand what it does;
- verify it matches the architecture;
- verify security implications;
- run tests;
- inspect the diff.

When code is ambiguous, explain the trade-off instead of guessing.

Prefer small commits and reversible changes.

## 18. Roadmap alignment notes

The roadmap is intentionally progressive. Do not build the whole final architecture on Day 1.

Examples:
- Early SQL days focus on database fundamentals before the FastAPI layer exists.
- Python days establish service/repository concepts before HTTP is added.
- FastAPI days introduce the API layer and operational foundations.
- Next.js days deepen frontend/BFF/auth/performance/state management.
- AWS/CI/CD comes after the local application is coherent.
- RAG comes after the core application and deployment foundations.
- Interview days convert the project into system-design and behavioral evidence.

The project may be continuously runnable, but features should be introduced in the roadmap's learning order unless a dependency forces an earlier scaffold.

## 19. Handling roadmap examples that are intentionally simplified

The roadmap is a learning roadmap, not a complete production specification.

When a sample is simplified or unsafe for production:
- preserve the educational goal;
- implement the concept safely in the actual repository;
- call out the difference briefly;
- do not copy insecure examples verbatim into production configuration.

Examples from the roadmap that require production hardening include hard-coded secrets/passwords and simplified cloud/deployment examples.

## 20. Definition of done for a daily increment

A Day N increment is not done merely because code was generated.

Done means:
- concept understood;
- implementation integrated with existing architecture;
- tests added/updated;
- relevant checks pass;
- errors handled;
- security considered;
- Git diff reviewed;
- commit created;
- interview takeaway captured.

## 21. Current priority

When the user supplies the current roadmap day, optimize for that day.

When the user does not specify a day, first determine the current project state and ask for the intended roadmap day rather than randomly implementing future features.

The repository should always move toward one coherent ShopSmart AI product, not a collection of disconnected tutorials.
