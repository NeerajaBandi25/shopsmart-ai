<!--
## Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: expanded guidance on verification, traceability, production engineering, dependencies, AI/RAG quality, UX/accessibility, comments, and complexity)
- Modified principles:
  - IV. Test-Driven Quality → expanded with verification requirements
  - V. Progressive Roadmap Fidelity → added production engineering default and complexity avoidance
- Added principles:
  - VI. Specification-to-Implementation Traceability
  - VII. Dependency Discipline
  - VIII. AI/RAG Quality Standards
  - IX. Frontend Coherence & Accessibility
  - X. Meaningful Technical Communication
- Removed sections: (none)
- Follow-up TODOs: (none)
-->

# ShopSmart AI Constitution

## Core Principles

### I. One Cohesive Product

ShopSmart AI MUST remain a single, integrated product and repository
combining e-commerce, AI-powered document assistant, and production
engineering concerns. Feature work (storefront, RAG, observability)
MUST converge into one deployable system — not a collection of
disconnected tutorials or separate portfolio repos.

**Rationale**: A unified codebase demonstrates end-to-end ownership,
realistic service boundaries, and interview-defensible architecture
decisions that isolated demos cannot.

### II. Layered Architecture

Every backend module MUST separate API/route handling, service/business
logic, repository/data access, and schema/model definitions into
distinct layers. Frontend modules MUST separate pages/routes, UI
components, data access (client/server), state management, and
validation/types. AI orchestration (ingestion, retrieval, generation)
MUST NOT collapse into HTTP handlers or data-access code.

**Rationale**: Explicit layer boundaries keep each concern independently
testable, replaceable, and reasoned about — critical for a system that
spans e-commerce transactions, document retrieval, and LLM generation.

### III. Security by Default

Secrets (API keys, DB passwords, JWT signing keys, AWS credentials)
MUST NEVER be committed to the repository; environment variables or a
secrets manager MUST be used. Browser-facing auth MUST use secure,
httpOnly cookies and CSRF protection where applicable. All database
queries MUST use parameterized statements — no string interpolation of
user input into SQL. File uploads MUST validate type, size, filename,
and authorization. Internal errors and stack traces MUST NOT be
returned to API consumers.

**Rationale**: The project handles payment-adjacent checkout workflows,
user authentication, and document uploads — attack surfaces where a
single shortcut can result in real-world exploitation.

### IV. Test-Driven Quality & Verification

Tests are part of implementation, not a cleanup task. Every increment
MUST include tests for the success path, validation failures, missing
resources, auth/permission failures, dependency failures, and relevant
concurrency/idempotency behavior. Features are NOT complete until they
pass appropriate automated tests, validate against specification,
satisfy relevant quality/security checks, include a clean diff, and
show evidence from verification gates. Coverage targets (80%+ unit, 90%+
critical paths) are goals, but meaningful coverage MUST be prioritized
over gaming the metric. AI/RAG tests MUST use controlled fixtures and
mock providers — the full test suite MUST NOT depend on paid external
API calls.

**Rationale**: The roadmap's progressive build means each day's code
becomes the foundation for the next. Untested layers compound risk and
block confident iteration on later phases. Verification gates catch
incomplete work before it creates downstream problems.

### V. Feature-Driven Architecture with Roadmap Guidance

Development MUST be feature-driven and architecture-aware. Features
SHOULD be implemented in the order that makes the product coherent,
production-safe, and deployable. The 75-day roadmap serves as a
technical scope and capability reference — it guides coverage of
required capabilities (SQL, Python, FastAPI, Next.js, CI/CD, AWS, AI/RAG,
system design) and progressive complexity, but MUST NOT mandate
implementation to follow individual roadmap days or a fixed learning
sequence. Implementation order MUST be justified by feature coherence,
architectural dependencies, and production-readiness requirements, not
by roadmap day numbers.

Code MUST be designed for deployability, observability, security,
maintainability, and failure handling — do not copy roadmap teaching
shortcuts when production-safe alternatives are available. Do NOT
introduce microservices, multi-agent orchestration, additional
infrastructure, or other structural complexity unless a current feature
requirement justifies it (premature complexity is technical debt).

**Rationale**: A feature-driven approach ensures the product is usable
and coherent at every stage. The roadmap ensures all required technical
capabilities are eventually covered and complexity grows progressively,
but rigid day-by-day adherence can force artificial ordering or leave
the product non-functional between phases. Production engineering from
the start means the final system is genuinely deployable, not a
retrofitted prototype.

### VI. Specification-to-Implementation Traceability

Feature implementation MUST remain traceable to its specification, plan,
tasks, tests, and acceptance criteria. Use Spec Kit's analyze/converge
workflow to detect gaps and create remediation tasks. Gaps between spec
and implementation MUST be resolved before a feature is considered done
— either the code MUST match the spec, or the spec MUST be updated with
explicit rationale for the deviation.

**Rationale**: A feature that matches its spec can be defended in review
and in an interview. Undocumented deviations create confusion and
increase the risk of incomplete or incorrect implementations.

### VII. Dependency Discipline

Do NOT introduce packages without clear need. Prefer maintained,
well-established dependencies. Pin or lock versions through the
appropriate package manager (package-lock.json, poetry.lock, requirements.txt).
Review dependency and security implications before adding. Minimize
transitive dependencies and keep the dependency tree shallow where
practical.

**Rationale**: Every dependency increases attack surface, build time,
and maintenance burden. Pinned versions prevent surprise breakage from
upstream changes and allow reproducible builds.

### VIII. AI/RAG Quality Standards

AI features MUST be testable without depending on paid external APIs.
Retrieval quality, grounding/citation accuracy, failure modes, latency,
cost, and regression behavior SHOULD be measurable where relevant.
Retrieval-augmented generation MUST NOT fabricate facts; the assistant
MUST clearly state when an answer is not supported by retrieved
documents. Chunking strategies MUST be tested rather than blindly
accepting fixed parameters. Model provider logic MUST be abstracted to
support local, mock, or alternative implementations for testing.

**Rationale**: Grounded AI features require measurable quality; testing
without expensive API calls is essential for developer productivity and
confidence. Abstracted providers keep options open and enable fast
iteration.

### IX. Frontend Coherence & Accessibility

The frontend MUST use a coherent ShopSmart design system across all
pages. Every user-facing component and flow MUST include responsive
behavior, loading states, empty states, success feedback, and error
handling. WCAG 2.2 AA-oriented accessibility practices MUST be followed
(semantic HTML, ARIA labels, keyboard navigation, color contrast,
screen-reader support). Full WCAG compliance verification requires
manual testing with assistive technologies and expert review.

**Rationale**: Consistent design creates a professional impression and
reduces user confusion. Accessible experiences serve all users and are
often legally required. Proper state handling prevents confusion when
data is loading or empty.

### X. Meaningful Technical Communication

Comments MUST explain non-obvious rationale, business rules, security
decisions, concurrency decisions, trade-offs, or operational
constraints. Comments MUST NOT merely restate what the code does —
well-named identifiers and clear structure already communicate that.
Commit messages MUST clearly state the intent and rationale of the
change. Code reviews MUST verify that implementation matches specification
and that deviations are explicitly justified.

**Rationale**: Meaningful comments and commit messages speed up
debugging, help future maintainers (including the original author
months later), and serve as evidence of intentional design decisions
during interviews.

## Technology & Architecture Constraints

- **Primary stack**: Next.js (frontend/BFF) → FastAPI (backend) →
  PostgreSQL (system of record) → Redis (cache/rate-limiting).
- **AI path**: document upload → ingestion → chunking → embeddings →
  vector store → retrieval → LLM generation → grounded answer with
  source citations → streaming response.
- **Database integrity**: foreign keys, constraints, indexes,
  transactions for multi-step operations, row-level locking for
  inventory-sensitive checkout. Migrations via Alembic — no ad-hoc
  schema mutations.
- **Checkout correctness**: payment/order state and inventory changes
  MUST NOT leave inconsistent partial state. Idempotency is mandatory
  for retriable operations.
- **Redis discipline**: Redis is a performance layer, not the source
  of truth. Every cache MUST define key design, TTL/invalidation
  strategy, miss behavior, and degradation behavior when Redis is
  unavailable.
- **No premature services**: extract a service only when a genuine
  deployment or domain boundary requires it.
- **Observability**: structured logs, request/correlation IDs, health
  and readiness endpoints, error monitoring, latency/error-rate
  metrics.
- **Containers**: small trusted base images, non-root execution,
  cache-friendly dependency layers, environment-driven configuration,
  health checks.

## Development Workflow & Quality Gates

- **Before modifying code**: inspect existing files and architecture,
  search for existing implementations, reuse stable project
  conventions, avoid duplicate utilities.
- **Daily increment protocol**: identify the day's concept → inspect
  repo state → connect to prior work → implement smallest
  production-quality change → add tests → run checks → review diff →
  commit → capture interview takeaway.
- **Definition of done**: concept understood, implementation integrated
  with existing architecture, tests added/updated, relevant checks pass,
  errors handled, security considered, specification traceability
  verified, diff reviewed, commit created, interview takeaway captured.
- **CI gates**: backend tests, frontend tests/build, formatting/lint/
  type checks, migration validation. PRs MUST fail fast on broken
  gates. Deployment MUST only happen from a known-good commit.
- **Commit hygiene**: small, reversible commits. No generated noise.
  Commit message clearly states intent and rationale.
- **Verification gates**: features MUST pass all applicable quality,
  security, and acceptance tests before merging. Use Spec Kit's
  analyze/converge to detect gaps before work is declared complete.

## Governance

This constitution is the highest-authority governance document for the
ShopSmart AI project. All implementation decisions, code reviews, and
architectural changes MUST comply with the principles above.

**Amendment procedure**:

1. Propose the change with rationale in writing.
2. Evaluate impact on existing code and roadmap alignment.
3. Update this document with the amended content.
4. Increment the version per semantic versioning:
   - MAJOR: principle removal or backward-incompatible redefinition.
   - MINOR: new principle or materially expanded guidance.
   - PATCH: clarification, wording, or non-semantic refinement.
5. Record the amendment date.

**Compliance review**: every PR and code review MUST verify alignment
with these principles. Deviations MUST be explicitly justified and
documented in the PR description.

**Guidance file**: the project's `CLAUDE.md` serves as the runtime
development guidance companion to this constitution.

**Version**: 1.1.0 | **Ratified**: 2026-09-15 | **Last Amended**: 2026-09-15
