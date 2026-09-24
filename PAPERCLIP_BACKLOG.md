# Paperclip Project Backlog: ShopSmart AI Implementation

**Derived from**: Engineering Plan: ShopSmart AI Authentication Foundation (plan.md v1.0)  
**Generated**: 2026-09-24  
**Status**: `in_review` — awaiting CEO acceptance  
**Owner**: CEO (90a45767-ffdc-4b7b-b21c-07c75431db02)  

---

## 1. Epics & Features

### EPIC-1: Foundation & Safety (Phase 1 — Weeks 1-2)
**Objective**: Establish the data foundation and security baseline.  
**Dependencies**: Nothing (infrastructure setup).  
**Priority**: P0 — Must complete before all other work.

| Task ID | Title | Priority | Acceptance Criteria | Dependencies | Recommended Owner |
|---------|-------|----------|---------------------|--------------|-------------------|
| T1 | Set up PostgreSQL + Alembic migrations | P1 | PostgreSQL instance running; `alembic upgrade head` creates users, sessions, login_attempts tables; models can create/read records | None | Full-Stack Engineer |
| T2 | Fix SECRET_KEY + add Redis fallback | P1 | `config.py:19` has no default `dev-secret-key-change-in-production`; `SECRET_KEY` required env var; RateLimiter tries Redis first, falls back to in-memory | T1 (database must be verified for Redis connection string format) | Full-Stack Engineer |
| T3 | Add CI pipeline (GitHub Actions) | P1 | `.github/workflows/test.yml` runs `cd backend && pytest`, `cd frontend && npm test`, `npm run lint`, `npm run format:check` on every PR; fails fast on breakage | T1 (database needed for pytest), T2 (SECRET_KEY env var format confirmed) | QA/Security Engineer |
| T4 | Security gates for merges | P1 | Merge blocked if: weak passwords accepted, rate limit not enforced, secure cookie flags missing, cross-user access not returning 403 | T1-T3 (database, SECRET_KEY, CI pipeline all operational) | QA/Security Engineer |

### EPIC-2: Authentication Harden (Phase 2 — Weeks 3-5)
**Objective**: Harden auth flow and verify security integrations.  
**Dependencies**: Priorities 1-2 (database, SECRET_KEY configured).  
**Priority**: P1 — All auth-critical work.

| Task ID | Title | Priority | Acceptance Criteria | Dependencies | Recommended Owner |
|---------|-------|----------|---------------------|--------------|-------------------|
| T5 | Cookie refresh integration | P3 | `session_refresh.py` verifies T050A passes; `Set-Cookie: Max-Age=2592000` refreshed on every authenticated request; rolling 30-day inactivity window confirmed | T1-T2 (database, SECRET_KEY configured) | Full-Stack Engineer |
| T6 | CSRF validation as defense-in-depth | P1 | CSRF token validation added to `/auth/register`, `/auth/login`, `/auth/logout` endpoints; `X-CSRF-Token` header validated against `session.csrf_token` | T1 (database for session csrf_token storage) | Full-Stack Engineer |
| T7 | Session timeout tests (T097-T099) | P2 | T097: 30-day inactivity → 401; T098: inactivity counter reset works; T099: indefinite validity with continuous activity; no absolute expiration cap | T5 (cookie refresh verified) | QA/Security Engineer |
| T8 | Rate limit headers | P2 | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` added to 429 responses | T1 (database + rate limiter operational) | Full-Stack Engineer |

### EPIC-3: Deployment & Observability (Phase 3 — Weeks 6-8)
**Objective**: Containerize, automate, and prepare for production.  
**Dependencies**: Priorities 1-4 (database, SECRET_KEY, CI, cookie refresh all verified).  
**Priority**: P2 — Production readiness.

| Task ID | Title | Priority | Acceptance Criteria | Dependencies | Recommended Owner |
|---------|-------|----------|---------------------|--------------|-------------------|
| T9 | Dockerfile + docker-compose.yml | P5 | Backend Dockerfile (FastAPI + uvicorn + alembic + Redis optional); Frontend Dockerfile (Next.js); `docker-compose.yml` with backend, frontend, Redis services; health checks; environment-driven config | T1 (database URL), T2 (Redis config), T4 (CI pipeline) | Full-Stack Engineer |
| T10 | Configure production CORS | P2 | `cors_origins` updated for production domains (not localhost-only) | T1 (database configured, deployment context established) | QA/Security Engineer |
| T11 | Health check + readiness probe | P2 | `/health` endpoint `{status: "ok"}` (always 200); `/readiness` endpoint `{status: "ready"}` (checks DB connectivity) | T1 (database) | Full-Stack Engineer |
| T12 | Observability foundations | P3 | Structured logs with timestamp, level, message, context; request IDs; basic metrics; auth/authorization audit trail | T4 (CI pipeline running in production-like environment) | QA/Security Engineer |

---

## 2. Implementation Task Dependencies Graph

```
T1 → T2 → T3 → T4
   ↓    ↓    ↓
T5 → T6 → T7 → T8
   ↓    ↓    ↓
T9 → T10 → T11 → T12

Within Foundational (Phase 2):
  T1, T2, T5, T6 can run in parallel (different files, no blocking deps)
  T3 depends on T1 + T2
  T4 depends on T1 + T2 + T3
  T7 depends on T5
  T8 depends on T1
  T9 depends on T1 + T2 + T4
  T10 depends on T1
  T11 depends on T1
  T12 depends on T4

User Story flow (post-Foundational):
  T13-T17: User Story 1 (Registration, P1) — depends on T1-T2
  T18-T22: User Story 2 (Login, P1) — depends on T1-T2 + US1
  T23-T26: User Story 3 (Logout, P1) — depends on T1-T2 + US2
  T27-T31: User Story 4 (Authorization, P1) — depends on T1-T2 + US2
  T32-T35: User Story 5 (Account, P2) — depends on T1-T2 + US4
```

---

## 3. Organization Proposal

### CEO Role (d44e70ab-fc7d-416a-8673-4ab161ac8149)
- Review company health and product goals
- Create and prioritize work only when explicitly authorized by a human
- Break approved work into bounded tasks with clear acceptance criteria
- Delegate implementation to the Full-Stack Engineer and independent verification to the QA & Security Reviewer
- Coordinate progress, require evidence from relevant checks, and review the final diff and test report before declaring work complete
- Escalate blockers, uncertainty, security concerns, and failed verification to the human
- **Do not directly modify the application unless a human explicitly authorizes that exception for coordination needs**

### CTO Role (proposed hire)
- Code, bugs, features, infra, devtools — priorities 1-5 from Phase 1-3
- Lead technical architecture and implementation decisions
- Own EPIC-1, EPIC-2 (primary)
- Code review and technical quality gatekeeping

### Full-Stack Engineer (proposed hire)
- Implement all backend and frontend tasks
- T1, T2, T5, T6, T9, T11 (primary ownership)
- Work across the full stack: FastAPI backend, Next.js frontend, database, DevOps
- Coordinate with QA/Security Engineer on integration points

### QA & Security Engineer (proposed hire)
- Independent verification and test validation
- T3 (CI pipeline creation + testing), T4 (security gates)
- T7 (session timeout tests), T8 (rate limit headers), T10 (CORS), T12 (observability)
- Verify all tests pass (red phase → green phase → refactor)
- Security review of all merges
- Test coverage enforcement (Constitution Principle IV: 100% FR coverage)

### Reporting Structure
```
CEO
└── CTO (proposed hire)
    ├── Full-Stack Engineer (proposed hire)
    │   ├── Backend implementation
    │   ├── Frontend implementation
    │   └── DevOps/Deployment
    └── QA & Security Engineer (proposed hire)
        ├── Test validation
        ├── Security review
        └── Quality gates
```

---

## 4. Proposed Agent Hires

| Role | Paperclip Issue ID | Responsibilities | Priority |
|------|-------------------|------------------|----------|
| **CTO** | CTO-001 | Lead technical architecture; own EPIC-1, EPIC-2; code review; technical decisions | High |
| **Full-Stack Engineer** | FE-001 | Implement all backend/frontend tasks; T1, T2, T5, T6, T9, T11 primary ownership | High |
| **QA & Security Engineer** | QA-001 | Independent verification; test validation; security gates; T3, T4, T7, T8, T10, T12 primary ownership | High |

**Hire Notes**:
- All three roles require explicit human approval before creation
- CTO should be technical lead; Full-Stack Engineer should be proficient in FastAPI + Python + Next.js + TypeScript; QA/Security Engineer should have strong test automation and security testing experience
- All hires operate under the delegation model per CEO AGENTS.md: CTO owns code/infra, QA owns verification, CEO coordinates and authorizes
- No agent should become the default implementer — CEO retains final approval gate for all production merges

---

## 5. Acceptance Criteria for This Backlog

- [ ] All epics, tasks, dependencies, and priorities are documented above
- [ ] Organization proposal (CEO/CTO/Full-Stack Engineer+QA) is reviewed and approved
- [ ] Proposed agent hires have been submitted for human approval
- [ ] No application source code has been modified (verified via `git diff --name-only`)
- [ ] All task acceptance criteria are verifiable without running the full application
- [ ] Dependencies are acyclic and logically consistent with plan.md priorities
- [ ] Recommended owners are clearly assigned and aligned with delegation model

---

## 6. Verification (Do Not Modify Application Source)

**Git state check** (run to verify no unintended changes):
```bash
git diff --name-only
# Expected: Only PAPERCLIP_BACKLOG.md added/modified, no backend/ or frontend/ source files
```

**Test/lint/typecheck** (run relevant checks, not full workspace):
```bash
# Lint only the new backlog file
ruff check PAPERCLIP_BACKLOG.md 2>/dev/null || echo "ruff not available or no issues"

# Verify plan.md still references the same priorities
# Verify tasks.md format consistency
```