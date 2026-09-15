# Implementation Plan: User Authentication and Account Foundation

**Branch**: `001-user-auth-foundation` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-user-auth-foundation/spec.md`

## Summary

Implement production-ready user authentication system for ShopSmart AI enabling email/password registration, login, logout, secure session management, and authorization boundaries. This is the foundational feature required for all downstream features (cart, checkout, orders, document uploads, AI chat). The implementation uses a server-side session model (database/Redis storage, secure httpOnly cookies), enforces single-session-per-user concurrency, and follows security-by-default principles: parameterized queries, CSRF protection, bcrypt password hashing, rate limiting on login, and 403/401 authorization enforcement.

## Technical Context

## Technical Context

**Authentication Model**: Server-side sessions (not JWT)
- Session identifier stored in secure httpOnly cookie (transmitted to client)
- Session state stored server-side in PostgreSQL (users, session data, activity timestamp, flags)
- Single-session-per-user enforced: Row-level locking (FOR UPDATE) on user table during login to prevent concurrent session creation
- Session validation: Extract session_id from cookie → lookup in sessions table → verify is_active, not expired by inactivity → update last_activity AND refresh session cookie Max-Age
- Logout: Mark session is_active = FALSE
- Password change: Invalidate all existing sessions for user (set is_active = FALSE), force re-login
- Session cookie: httpOnly, Secure, SameSite=Strict, Max-Age=2592000 (30 days from last activity) — refreshed on every authenticated request to maintain rolling window

**Concurrency & Transaction Safety**:
- Login creates new session with row-level locking: BEGIN → SELECT user FROM users WHERE id = ? FOR UPDATE (locks row) → IF existing active session THEN DELETE/invalidate old session END → INSERT new session → COMMIT
- This prevents race condition where simultaneous logins could create multiple active sessions
- Session lookup uses prepared statements for parameterization and atomic visibility

**Session Lifecycle**:
1. Created on successful login (is_active = TRUE, last_activity = NOW())
2. Session cookie set with Max-Age = 2592000 (30 days from NOW())
3. Extended on activity (last_activity updated on each authenticated request; session cookie Max-Age refreshed to 30 days from NOW() to maintain rolling window)
4. Invalidated on logout (is_active = FALSE)
5. Invalidated on password change (all sessions for user set is_active = FALSE)
6. Expired after 30 days of inactivity (NOW() - last_activity > 30 days; rolling inactivity only, no absolute expiration cap)
7. Sessions remain valid indefinitely while user is active (both server-side last_activity AND client-side cookie lifetime are continuously refreshed)
8. Cleanup: Soft-delete (keep for audit); can be hard-deleted after retention period

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)

**Primary Dependencies**: 
- Backend: FastAPI, SQLAlchemy, bcrypt, asyncpg (PostgreSQL async driver)
- Frontend: Next.js 14+, TypeScript, React Hook Form or similar for validation
- Infrastructure: PostgreSQL (users, sessions), Redis (optional: rate limiting, session cache)

**Storage**: PostgreSQL (system of record for users and sessions); optional Redis for rate limiting

**Testing**: pytest (backend unit/integration), pytest-asyncio (async DB tests), Playwright or Cypress (frontend integration tests)

**Target Platform**: Web browser (modern browsers supporting secure cookies, HTTPS)

**Project Type**: Full-stack web application (backend REST API + Next.js frontend + BFF)

**Performance Goals**: 
- Registration/login < 1 minute / < 30 seconds (user-perceived)
- API response time < 200ms p95 (typical auth endpoints)
- Support 1000+ concurrent authenticated users

**Constraints**: 
- HTTPS required; secure cookies (httpOnly, Secure, SameSite=Strict)
- Session timeout: 30 days inactivity (activity resets timer)
- Rate limiting: 5 failed login attempts per IP per 15-minute window
- No secrets committed; all environment-driven (DB connection, session keys, etc.)
- Single-session-per-user enforced at database level with row-level locking to prevent concurrent session creation race conditions

**Scale/Scope**: MVP v1 covers 5 user stories (P1/P2), 21 functional requirements, single-session-per-user, web-only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Security by Default (Principle III) ✓
- Secrets management: All credentials environment-driven (DB connection, session keys, CSRF tokens)
- Browser auth: Secure httpOnly cookies with HTTPS, CSRF protection required
- Database queries: Parameterized queries via SQLAlchemy ORM (no string interpolation)
- Input validation: User input validated on both frontend and backend
- Error handling: No stack traces returned to API consumers; generic error messages to users
- **Status**: PASS — plan includes all required security practices

### Test-Driven Quality & Verification (Principle IV) ✓
- Unit tests: Business logic, password hashing, session management
- Integration tests: API endpoints (auth, profile), database transactions
- Auth/permission tests: Authorization boundaries (403 cross-user access, 401 invalid tokens)
- Validation tests: Password strength, email format, rate limiting
- No external API dependencies: bcrypt and session logic fully testable locally
- **Status**: PASS — all testable without external services

### Layered Architecture (Principle II) ✓
- Backend separation: routes (FastAPI) → services (business logic) → repositories (data access) → models (schemas)
- Frontend separation: pages/routes → UI components → data access (client/BFF) → state → validation
- No collapsed concerns: Auth logic isolated from HTTP handlers
- **Status**: PASS — plan enforces explicit layers

### Dependency Discipline (Principle VII) ✓
- Dependencies: FastAPI, SQLAlchemy, bcrypt, asyncpg — all established, maintained packages
- No bloat: Minimal transitive dependencies; bcrypt and FastAPI are standard choices
- Version pinning: Will use lock files (requirements.txt, package-lock.json)
- **Status**: PASS — dependencies justified and well-vetted

### Frontend Coherence & Accessibility (Principle IX) ✓
- Design system: Registration/login pages follow ShopSmart design patterns (responsive, consistent styling)
- States: Loading, error, success, and empty states included in UI design
- Accessibility: Semantic HTML, ARIA labels for form inputs, keyboard navigation (Tab through fields), color contrast minimum AA
- **Status**: PASS — design includes coherence and a11y practices

### Production Engineering by Default (Principle V) ✓
- No teaching shortcuts: Uses bcrypt (industry standard), server-side sessions (not simplified JWT), CSRF tokens
- Deployability: Environment-driven config, health endpoints included, observability (structured logging)
- No premature complexity: Single-session enforced (simpler than multi-device), no multi-agent orchestration
- **Status**: PASS — production-ready from day one

**Overall Constitution Check**: ✓ PASS — no violations

## Project Structure

### Documentation (this feature)

```text
specs/001-user-auth-foundation/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (research decisions)
├── data-model.md        # Phase 1 output (entity schemas)
├── contracts/           # Phase 1 output (API contracts)
│   ├── auth-api.md
│   └── session-api.md
├── quickstart.md        # Phase 1 output (validation guide)
└── tasks.md             # Phase 2 output (task decomposition)
```

### Source Code Structure

```text
# Backend (FastAPI)
backend/
├── src/
│   ├── core/
│   │   ├── config.py           # Environment variables, settings
│   │   ├── security.py         # Password hashing, CSRF, session logic
│   │   ├── exceptions.py       # Custom exception classes
│   │   └── logging.py          # Structured logging
│   ├── models/
│   │   ├── user.py             # Pydantic schemas for User input/output
│   │   └── session.py          # Pydantic schemas for Session
│   ├── repositories/
│   │   ├── user_repository.py  # Database access layer (SQLAlchemy)
│   │   └── session_repository.py
│   ├── services/
│   │   ├── auth_service.py     # Business logic (registration, login, authorization)
│   │   └── session_service.py  # Session management
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth_routes.py  # POST /auth/register, /auth/login, /auth/logout
│   │   │   ├── user_routes.py  # GET /users/profile, PUT /users/password
│   │   │   └── deps.py         # Dependency injection (current_user, db_session)
│   │   └── health.py           # Health/readiness checks
│   ├── database.py             # SQLAlchemy setup, session factory
│   └── main.py                 # FastAPI app initialization, middleware
├── migrations/                 # Alembic migrations (User, Session tables)
└── tests/
    ├── unit/
    │   ├── test_auth_service.py
    │   ├── test_password_hashing.py
    │   └── test_session_logic.py
    ├── integration/
    │   ├── test_auth_endpoints.py
    │   ├── test_authorization.py
    │   └── test_rate_limiting.py
    └── conftest.py             # Pytest fixtures (db, client, test users)

# Frontend (Next.js)
frontend/
├── src/
│   ├── app/
│   │   ├── auth/
│   │   │   ├── register/page.tsx
│   │   │   ├── login/page.tsx
│   │   │   └── logout/route.ts (BFF handler)
│   │   ├── account/
│   │   │   └── page.tsx          # Profile/settings page
│   │   ├── layout.tsx            # Root layout with nav/logout
│   │   └── page.tsx              # Public home or redirect logic
│   ├── components/
│   │   ├── auth-form.tsx         # Registration/login form component
│   │   ├── password-input.tsx    # Password strength indicator
│   │   └── error-alert.tsx       # Error state display
│   ├── lib/
│   │   ├── api-client.ts         # HTTP client for API calls
│   │   ├── auth-context.ts       # (Optional: minimal client state for loading/error)
│   │   └── validation.ts         # Email/password validation functions
│   └── types/
│       └── auth.ts               # TypeScript types (User, LoginRequest, etc.)
├── middleware.ts                 # Next.js middleware for protected routes
└── tests/
    ├── integration/
    │   ├── register.test.tsx
    │   ├── login.test.tsx
    │   └── logout.test.tsx
    └── unit/
        └── validation.test.ts

# Database
migrations/
└── alembic/
    └── versions/
        └── 001_create_users_and_sessions.py
```

**Structure Decision**: Full-stack web application (Option 2) with clear backend/frontend/database separation. Backend is FastAPI + PostgreSQL; frontend is Next.js + TypeScript. Follows constitution's layered architecture requirement: routes → services → repositories → models for backend; pages → components → API client → types for frontend.

## Complexity Tracking

No Constitution Check violations. Feature is straightforward authentication without premature complexity:
- Single-session enforcement (simpler than multi-device support)
- Server-side session storage (no multi-agent orchestration)
- Standard layered architecture (no microservices)
- Minimal dependencies (FastAPI, SQLAlchemy, bcrypt)

---

## Phase 0: Research (Outcomes)

*Research phase identifies key technical decisions and best practices.*

### Research Topics & Decisions

1. **Authentication Model: Server-Side Sessions vs. JWT**
   - Decision: Server-side sessions (NOT JWT)
   - Rationale: 
     - Session state stored server-side in PostgreSQL (source of truth)
     - Session identifier transmitted in secure httpOnly cookie (not accessible to JavaScript)
     - Enables atomic logout (immediate invalidation, not delayed by token expiry)
     - Enables password-change session invalidation (all sessions invalidated immediately)
     - Simpler security model for web apps (no token rotation, no token revocation complexity)
     - Supports single-session enforcement via database transactions
   - Alternatives: JWT (stateless, but requires token rotation and revocation complexity); OAuth (external service, out of scope)

2. **Password Hashing Algorithm Selection**
   - Decision: bcrypt (with 12 salt rounds)
   - Rationale: Industry-standard, resistant to GPU attacks, built-in salt handling
   - Alternatives: Argon2 (superior but heavier), PBKDF2 (acceptable but older)

3. **Single-Session Enforcement & Concurrency Safety**
   - Decision: Row-level database locking (FOR UPDATE) during login transaction
   - Rationale:
     - BEGIN TRANSACTION → SELECT user FOR UPDATE (locks row) → check/invalidate old sessions → INSERT new session → COMMIT
     - Prevents race condition where simultaneous logins could create multiple active sessions
     - Atomic operation: new session guaranteed to be only active session
   - Alternatives: Application-level locking (non-deterministic), optimistic locking (retry on conflict)

4. **Session Storage & Invalidation**
   - Decision: Server-side sessions in PostgreSQL (primary), optional Redis for cache/rate-limiting
   - Rationale: Enables atomic operations, supports soft-delete audit trail, row-level locking for concurrency
   - Invalidation: Set is_active = FALSE (not delete) for audit trail
   - Alternatives: Memcached (no transactions), in-memory (not distributed)

5. **CSRF Protection Strategy**
   - Decision: Double-submit cookie pattern via FastAPI middleware + SameSite=Strict
   - Rationale: Works with httpOnly cookies, easy to test, standard in FastAPI ecosystem
   - Alternatives: Synchronizer token pattern (same browser complexity), custom headers

6. **Rate Limiting Implementation**
   - Decision: Redis-backed rate limiter (with fallback to in-memory if Redis unavailable)
   - Rationale: Distributed, handles multi-instance deployments, respects Constitution's Redis discipline
   - Alternatives: Database-backed (simpler but slower), sliding window (more complex)

7. **Frontend Session Validation**
   - Decision: Middleware-level (Next.js middleware) + BFF routes for protected endpoints
   - Rationale: Server-side redirect on 401 (better UX), clear authorization boundary
   - Alternatives: Client-side redirect (less reliable), JWT validation in browser (violates httpOnly requirement)

**Output**: Decisions embedded in this plan; all clarifications resolved in spec phase (no separate research.md needed).

---

## Phase 1: Design & Contracts

### 1. Data Model

**Output**: `data-model.md` with entity definitions, validation rules, and state transitions.

**Entities**:

1. **User**
   - id (UUID, primary key)
   - email (string, unique, not null)
   - password_hash (string, not null)
   - created_at (timestamp)
   - updated_at (timestamp)
   - Constraints: Email must be valid RFC 5322; password hash via bcrypt; email unique across system

2. **Session**
   - id (UUID, primary key)
   - user_id (UUID, foreign key to User)
   - created_at (timestamp)
   - expires_at (timestamp, 30 days from creation or last activity)
   - last_activity (timestamp, updated on each request)
   - ip_address (string, for audit/security)
   - user_agent (string, for device tracking)
   - Constraints: Foreign key enforces user exists; expires_at updated on activity; on user logout, soft-delete or set expires_at to now

3. **LoginAttempt** (audit/rate limiting)
   - id (UUID, primary key)
   - email (string, not null)
   - ip_address (string, not null)
   - timestamp (timestamp)
   - success (boolean)
   - Constraint: Composite index on (ip_address, timestamp) for rate-limit queries

### 2. Interface Contracts

**Output**: API contracts in `contracts/` directory.

**Contracts**:

1. **Authentication API** (`contracts/auth-api.md`)
   - POST /auth/register → { email, password } → { user_id, email, created_at } or error
   - POST /auth/login → { email, password } → { user_id, email } (session cookie set) or 401
   - POST /auth/logout → {} → 204 or 401 (session invalidated)
   - GET /auth/me → {} → { user_id, email, created_at } or 401 (current user)

2. **User API** (`contracts/user-api.md`)
   - GET /users/profile → {} → { user_id, email, created_at } or 401
   - PUT /users/password → { current_password, new_password } → 204 or 400/401

3. **Authorization Headers & Response Codes**
   - All endpoints require session cookie (automatic in browser)
   - 200: Success
   - 201: Resource created
   - 204: Success with no content
   - 400: Validation error (bad email, weak password, etc.)
   - 401: Unauthorized (missing/invalid session)
   - 403: Forbidden (cross-user access attempt)
   - 409: Conflict (email already exists)

4. **CORS Configuration** (Next.js/FastAPI architecture per Correction #4)
   - **Development**: Allow http://localhost:3000 (Next.js dev server)
   - **Production**: Allow https://shopsmartai.example.com (deployed domain)
   - **Credentials**: True (allows secure httpOnly cookies to be sent cross-origin)
   - **Methods**: GET, POST, PUT, DELETE
   - **Headers**: Accept, Content-Type

### 3. Quickstart Validation Guide

**Output**: `quickstart.md` with runnable test scenarios.

Scenarios:

1. **Happy path: Registration → Login → Logout**
   - Prerequisites: Docker, PostgreSQL running, backend/frontend started
   - Steps:
     1. POST /auth/register with valid email/password
     2. Verify 201 response with user_id
     3. POST /auth/login with same credentials
     4. Verify 200 response; session cookie set in browser
     5. GET /auth/me → verify returns logged-in user
     6. POST /auth/logout → verify 204 response
     7. GET /auth/me → verify 401 Unauthorized (session cleared)

2. **Authorization boundary: Cross-user access blocked**
   - Prerequisites: Two registered users (user1, user2)
   - Steps:
     1. Log in as user1
     2. GET /api/orders/user2-id → verify 403 Forbidden
     3. Verify user1 cannot see user2's data

3. **Rate limiting: Multiple failed logins**
   - Prerequisites: Test account with known credentials
   - Steps:
     1. POST /auth/login with wrong password 5 times from same IP
     2. Verify first 5 return 401
     3. 6th attempt return 429 (rate limited)
     4. Wait 15 minutes or clear rate-limit counter
     5. Verify login works again

4. **Session timeout: Inactivity**
   - Prerequisites: Logged-in session
   - Steps:
     1. Log in successfully
     2. Wait 30 days (or mock clock in tests)
     3. GET /auth/me → verify 401 (session expired)

**Output files for Phase 1**:
- `data-model.md` — Entity definitions with validation and state transitions
- `contracts/auth-api.md` — Authentication API contract
- `contracts/user-api.md` — User profile API contract
- `quickstart.md` — Runnable validation scenarios

---

## Next Phase

Phase 2 (`/speckit-tasks`) will decompose this plan into atomic implementation tasks, task dependencies, and acceptance criteria for each task.

