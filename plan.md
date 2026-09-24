# Engineering Plan: ShopSmart AI Authentication Foundation

**Plan Version**: 1.0  
**Created**: 2026-09-24  
**Status**: `in_review` — awaiting board acceptance  
**Owner**: CEO (d44e70ab-fc7d-416a-8673-4ab161ac8149)  
**Issue**: TES-1 ShopSmart Engineering Assessment

---

## 1. Repository/Git state

- **Current branch**: `main` (up to date with 'origin/main')
- **Recent commits** (last 5):
  - `27ce10f` Merge pull request #2 from NeerajaBandi25/backend-security-hardening
  - `9d48829` feat(security): harden auth transactions csrf and password changes
  - `de01540` Merge pull request #1 from NeerajaBandi25/homepage-auth-dashboard-ui
  - `dbaa560` feat(frontend): complete homepage redesign and lint cleanup
  - `918cefa` feat: implement ShopSmart auth, frontend foundation, and test infrastructure
- **Uncommitted changes**: 99 modified files + 2 untracked files (plan.md at root, .freebuff/project-id)
  - **Pre-existing agent/infrastructure files**: `.claude/` (13 settings files), `.harness/` (10 hook/policy files), `.specify/` (14+ template/workflow files) — modified by the assessment harness, not part of the application codebase
  - **Application/project files**: `backend/` (42 source/test/migration/config files), `frontend/` (50+ source/component/asset files), root `CLAUDE.md`, `IMPLEMENTATION_SUMMARY.md`, `PROJECT_STATUS.md`, `TEST_VERIFICATION_REPORT.md`, migration files, config files — these represent the actual working tree state
  - **Do not modify or clean the repository** — all 99 modified files and 2 untracked files reflect the pre-existing working-tree state; no changes were created during this assessment
- **No `.env` files committed** — only `.env.example` templates exist
- **No Dockerfiles or CI/CD workflows** present in the repository

**Evidence**: `git log --oneline -5`, `git status --porcelain`

---

## 2. Frontend architecture

**Tech stack**: Next.js 14 (app-router), React 18, TypeScript, Tailwind CSS 4

**Directory structure** (`frontend/`):
- `src/app/` — Pages: `page.tsx` (Home), `layout.tsx`, `auth/layout.tsx`, `auth/register/page.tsx`, `auth/login/page.tsx`, `authenticated-layout.tsx`, `dashboard/page.tsx`, `account/page.tsx`
- `src/components/` — UI components: `registration-form.tsx`, `login-form.tsx`, `nav.tsx`, `HeroCampaign.tsx`, `PromoBanner.tsx`, `CategorySection.tsx`, `DiscoverySection.tsx`, `ui/` primitives (Input, Button, Alert, Card)
- `src/lib/api-client.ts` — Fetch wrappers with `credentials: 'include'` for cookie-based auth (register, login, logout, getProfile, getCsrfToken, changePassword)
- `src/styles/globals.css` — Global styles with Tailwind directives
- `jest.config.js` — Jest config with `ts-jest`, `jsdom` environment, `@testing-library/jest-dom`
- `package.json` — Scripts: `dev`, `build`, `start`, `lint`, `test`, `format`, `format:check`

**Key findings**:
- Home page (`page.tsx:29-91`) checks for session cookie presence via `cookies().has('session_id')` and passes `probeAuth` to `<Nav>` — avoids client-side auth probe that would always return 401 for signed-out visitors
- Registration form (`registration-form.tsx`) enforces client-side password strength validation (length ≥8, uppercase, lowercase, digit, special char) and displays password requirement indicators
- Login form (`login-form.tsx`) uses `api-client.login()` with `credentials: 'include'` to send session cookie
- API client (`api-client.ts:58-135`) wraps all fetch calls with `handleApiResponse()` which throws on 401 and extracts error detail/error_code
- No form of state management (Zustand/React Query) — API calls are imperative per component
- Tailwind config (`tailwind.config.js:1-12`) references content paths covering `src/**/*.{js,ts,jsx,tsx}`, `app/**/*.{js,ts,jsx,tsx}`, `components/**/*.{js,ts,jsx,tsx}`

**Evidence**: `frontend/src/app/page.tsx`, `frontend/src/lib/api-client.ts`, `frontend/package.json`, `frontend/jest.config.js`, `frontend/tailwind.config.js`

---

## 3. Backend architecture

**Tech stack**: FastAPI (Python 3.11), SQLAlchemy 2 + asyncpg (async PostgreSQL), Alembic migrations

**Directory structure** (`backend/src/`):
- `main.py:1-108` — FastAPI app initialization with lifespan, CORS middleware, session refresh middleware, exception handlers, health/readiness endpoints
- `api/v1/auth_routes.py:66-275` — Router with prefix `/auth`: register, login, logout, csrf, me endpoints
- `api/v1/user_routes.py:1-79` — Router with prefix `/users`: get_profile, change_password endpoints
- `api/v1/deps.py:1-56` — Dependency injection: `get_db()` yields AsyncSession, `get_current_user()` extracts user from session cookie
- `core/security.py:1-66` — `hash_password()` (bcrypt 12 rounds), `verify_password()`, `generate_session_id()`, `generate_csrf_token()`, `verify_csrf_token()` (constant-time compare)
- `core/config.py:1-57` — `Settings` (Pydantic BaseSettings) with all environment variables
- `core/rate_limiter.py:1-99` — In-memory RateLimiter (5 attempts/15min window per IP)
- `core/csrf.py:1-83` — `CSRFTokenManager` (token generation/validation with 24hr expiry)
- `core/exceptions.py:1-84` — Custom exception hierarchy: AppException(400/401/403/429/409), ValidationError, AuthenticationError, AuthorizationError, RateLimitError, ConflictError
- `database.py` — References `AsyncSessionLocal`, `init_db()`, `close_db()`
- `models/base.py` — BaseModel with id, created_at, updated_at
- `models/user.py:1-42` — User table: email (unique, indexed, CheckConstraint RFC 5322 format), password_hash, relationships to sessions
- `models/session.py:1-66` — Session table: user_id (FK), last_activity (timezone-aware), ip_address (INET), user_agent, is_active, csrf_token
- `models/login_attempt.py` — Audit trail for rate limiting
- `services/auth_service.py:1-293` — AuthService with register_user, login_user, logout_user, change_password (TDD-written)
- `repositories/` — user_repository, session_repository, login_attempt_repository (DB access layer)
- `middleware/session_refresh.py:1-64` — BaseHTTPMiddleware that refreshes session cookie Max-Age on authenticated requests

**Auth flow** (per `auth_routes.py`):
1. `POST /api/v1/auth/register` → validates email format + password strength → hashes with bcrypt 12 rounds → creates User + SessionAttempt → returns `RegisterResponse(user_id, email, created_at)` + 201
2. `POST /api/v1/auth/login` → validates credentials → rate-limit check (5/15min) → single-session enforcement (invalidates previous session) → creates Session record → sets `Set-Cookie: session_id=<uuid>; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000; Path=/` → returns `LoginResponse(user_id, email)` + 200
3. `GET /api/v1/auth/me` → depends on `get_current_user` → validates session via `validate_session()` → updates `last_activity` → returns `MeResponse(user_id, email, created_at)` + 200
4. `POST /api/v1/auth/logout` → invalidates session (is_active=FALSE) → clears cookie (Max-Age=0) → returns 204
5. `GET /api/v1/auth/csrf` → validates session + csrf_token → returns `CsrfResponse(csrf_token)` + 200
6. `PUT /api/v1/users/password` → validates session + CSRF token → verifies current_password → updates password_hash → invalidates all sessions → returns 204

**Key files**: `backend/src/main.py`, `backend/src/api/v1/auth_routes.py`, `backend/src/core/security.py`, `backend/src/core/config.py`, `backend/src/services/auth_service.py`

**Evidence**: `backend/src/main.py`, `backend/src/api/v1/auth_routes.py`, `backend/src/core/security.py`, `backend/src/core/config.py`, `backend/src/services/auth_service.py`

---

## 4. Database architecture

**PostgreSQL** with SQLAlchemy 2 models, Alembic migrations

**Tables** (per data-model.md and model definitions):

- **users**: id (UUID PK), email (VARCHAR 255, UNIQUE, CHECK regex RFC 5322), password_hash (VARCHAR 255, NOT NULL), created_at (TIMESTAMP, DEFAULT NOW()), updated_at (TIMESTAMP, DEFAULT NOW()), Index on created_at, UniqueConstraint on email
- **sessions**: id (UUID PK, UUID v4), user_id (UUID FK → users.id ON DELETE CASCADE), created_at (TIMESTAMP, DEFAULT NOW()), last_activity (TIMESTAMP, timezone-aware, DEFAULT NOW(), server_default=func.now()), ip_address (INET, NOT NULL), user_agent (VARCHAR 500, NOT NULL), is_active (BOOLEAN, DEFAULT TRUE), csrf_token (VARCHAR 64, NOT NULL), Index on (user_id, is_active), Index on last_activity
- **login_attempts**: id (UUID PK), email (VARCHAR 255, NOT NULL), ip_address (INET, NOT NULL), attempted_at (TIMESTAMP, DEFAULT NOW()), success (BOOLEAN, NOT NULL), failure_reason (VARCHAR 100) — CHECK: (success=TRUE AND failure_reason IS NULL) OR (success=FALSE AND failure_reason IS NOT NULL), Index on (ip_address, attempted_at)

**Alembic migrations** (2 found):
- `migrations/versions/001_create_users_sessions_tables.py` — Creates users, sessions, login_attempts tables
- `migrations/versions/002_add_session_csrf_token.py` — Adds csrf_token column to sessions

**Indexes** (critical query paths):
- `idx_users_email` — UNIQUE on users.email
- `idx_users_created_at` — on users.created_at
- `idx_sessions_user_id_active` — on (sessions.user_id, sessions.is_active) — essential for single-session enforcement
- `idx_sessions_last_activity` — on sessions.last_activity — supports inactivity timeout cleanup
- `idx_login_attempts_ip_timestamp` — on (login_attempts.ip_address, login_attempts.attempted_at) — essential for rate-limit queries

**Session validation logic** (per `data-model.md:248-256` and `session_validator.py`):
1. Extract session_id from cookie
2. Look up Session by id
3. Check is_active = TRUE → 401 if not
4. Check NOW() - last_activity > 30 days → 401 if inactivity timeout exceeded
5. If valid, update last_activity = NOW() (extend timeout to NOW() + 30 days)
6. Extract user_id and verify user still exists → 401 if user deleted
7. **No absolute expiration cap**: Session remains valid indefinitely while actively used (last_activity kept current)

**Evidence**: `backend/src/models/user.py:14-38`, `backend/src/models/session.py:20-63`, `backend/tests/conftest.py:22-31`, `specs/001-user-auth-foundation/data-model.md:145-192`

---

## 5. Authentication and security

### Strengths (with exact file/line references):

- **bcrypt password hashing** (`backend/src/core/security.py:9-19`): `hash_password()` uses `bcrypt.gensalt(rounds=12)`, `verify_password()` uses `bcrypt.checkpw()`. Unit tests `test_auth_service.py:124-138` verify hash starts with `$2b$` and `verify_password()` returns True/False correctly.
- **Secure session cookies** (`backend/src/api/v1/auth_routes.py:143-144`): `Set-Cookie: session_id=<uuid>; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000; Path=/`. Logout clears cookie (`auth_routes.py:186-194`) with `Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT`.
- **Email validation** (`backend/src/models/user.py:34-37`): CheckConstraint `"email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'`. AuthService `_is_valid_email()` (`auth_service.py:252-266`) uses simplified RFC 5322 regex.
- **Password strength enforcement** (`auth_service.py:269-293`): `_is_strong_password()` requires ≥8 chars, uppercase, lowercase, digit, special char. Validated in both `AuthService.register_user()` (`auth_service.py:53-58`) and `registration-form.tsx:41-48` client-side.
- **Generic error messages** (`auth_routes.py:218,237`): "Invalid email or password" never reveals whether email exists.
- **Single-session enforcement** (`auth_service.py:156-157`): `invalidate_user_sessions(user.id)` called before creating new session. Tests `test_auth_service.py:243-289` verify second login invalidates first.
- **CSRF protection** (`user_routes.py:45-79`): `change_password` requires valid CSRF token stored in session (`verify_csrf_token(x_csrf_token, session.csrf_token)` at `user_routes.py:70`). Missing token → 403 `AuthorizationError`. Token mismatch → 403.
- **Rate limiting** (`core/rate_limiter.py:10-46`): In-memory, 5 failed attempts per IP per 15-min window. 6th attempt raises `RateLimitError` (429). Integration tests `test_auth_endpoints.py:392-419` verify 5×401 then 429.
- **Exception hierarchy** (`core/exceptions.py:6-84`): All exceptions extend `AppException` with proper status codes and error_codes. FastAPI exception handlers in `main.py:54-78` return JSON with `{detail, status_code, error_code}` never exposing stack traces.

### Gaps (with exact file/line references):

- **In-memory rate limiter only** (`core/rate_limiter.py:10-22`): Uses `defaultdict(list)` in process memory. `rate_limiter.py:66-69` creates global instance. Won't scale across multiple backend instances; lost on process restart. `redis_url` config exists in `config.py:31` but is `Optional[str] = None` — no Redis backend implemented.
- **CSRF token manager is in-memory global** (`core/csrf.py:83`): `csrf_manager = CSRFTokenManager()` — tokens not persisted across restarts. Not integrated into `user_routes.py` except for `/users/password` endpoint.
- **Weak default SECRET_KEY** (`config.py:19`): `secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")`. Algorithm is HS256 (`config.py:20`) — symmetric, not used for cookie signing (bcrypt handles passwords; cookies use random UUIDs).
- **CORS restricted to localhost** (`config.py:42-45`): `cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]`. Would need updating for production domains.
- **No HTTPS enforcement**: Code sets `Secure` flag on cookies but no server-level HTTPS termination guaranteed.
- **Cookie refresh middleware integration unproven** (`middleware/session_refresh.py:1-64`): Middleware exists and is registered in `main.py:50`, but T050A test (`test_auth_endpoints.py:433-440`) is a `pass` stub. The middleware refreshes `Set-Cookie: Max-Age=2592000` on every authenticated request, but end-to-end verification is missing.
- **Session timeout: rolling inactivity, no absolute cap** (`config.py:24`): `session_timeout_seconds: int = 30 * 24 * 60 * 60` (30 days). Middleware (`session_refresh.py:52-57`) refreshes Max-Age=2592000. Spec.md `assumptions L173`: "30 days of rolling inactivity; no absolute expiration cap". No test verifies sessions remain valid beyond 30 calendar days with continuous activity.
- **CSRF not validated on auth endpoints** (`auth_routes.py:69-150`): `/auth/register`, `/auth/login`, `/auth/logout` rely on `SameSite=Strict` only. No `X-CSRF-Token` header validation on these endpoints. CSRF recommendations without evidence of actual vulnerability should be classified as defense-in-depth (see reclassification below).

**Evidence**: `backend/src/core/security.py`, `backend/src/core/rate_limiter.py`, `backend/src/core/config.py`, `backend/src/core/csrf.py`, `backend/src/api/v1/auth_routes.py`, `backend/src/services/auth_service.py`, `backend/tests/integration/test_auth_endpoints.py:390-427`, `backend/tests/unit/test_auth_service.py:332-465`, `specs/001-user-auth-foundation/spec.md:99-101`, `specs/001-user-auth-foundation/REMEDIATION_REPORT.md:44-48`

---

## 6. API architecture

**Base URL**: `/api/v1` (per `config.py:34` and route prefixes in `auth_routes.py:66` and `user_routes.py:17`)

**Auth API endpoints** (`auth_routes.py:66-275`):

| Endpoint | Method | Description | Status |
|---|---|---|---|
| `POST /api/v1/auth/register` | register | Create user | 201 |
| `POST /api/v1/auth/login` | login | Authenticate + create session | 200 |
| `POST /api/v1/auth/logout` | logout | Invalidate session | 204 |
| `GET /api/v1/auth/csrf` | csrf | Get CSRF token | 200 |
| `GET /api/v1/auth/me` | me | Get current user | 200 |

**User API endpoints** (`user_routes.py:1-79`):

| Endpoint | Method | Description | Status |
|---|---|---|---|
| `GET /api/v1/users/profile` | profile | Get authenticated user profile | 200 |
| `PUT /api/v1/users/password` | password | Change password (requires CSRF) | 204 |

**Request/Response models** (Pydantic `BaseModel`):

- `RegisterRequest(email, password)` → `RegisterResponse(user_id, email, created_at)`
- `LoginRequest(email, password)` → `LoginResponse(user_id, email)`
- `MeResponse(user_id, email, created_at)`
- `CsrfResponse(csrf_token)`
- `PasswordChangeRequest(current_password, new_password)`
- `ProfileResponse(user_id, email, created_at)`

**Error envelope** (per `main.py:54-64` and `exceptions.py`): `{detail, status_code, error_code}` for all `AppException` subclasses. General exceptions return `{detail: "Internal server error", status_code: 500, error_code: "INTERNAL_ERROR"}`.

**Set-Cookie headers** on login: `HttpOnly; Secure; SameSite=Strict; Max-Age=2592000` (30 days). On logout: `Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT`.

**CSRF** on state-changing endpoints: `X-CSRF-Token` header validated against `session.csrf_token`. Omitted → 403. Invalid → 403. Currently only enforced on `/users/password`.

**API contract references** (`specs/001-user-auth-foundation/contracts/auth-api.md` and `contracts/user-api.md`): All response schemas, error envelopes, cookie formats, and testing scenarios documented.

**Evidence**: `backend/src/api/v1/auth_routes.py:69-150`, `backend/src/api/v1/user_routes.py:31-79`, `backend/src/core/exceptions.py`, `specs/001-user-auth-foundation/contracts/auth-api.md`, `specs/001-user-auth-foundation/contracts/user-api.md`

---

## 7. Tests and test health

**Test structure** (3 layers, 25+ tests total):

### Unit tests (`backend/tests/unit/test_auth_service.py:1-509`):
- 12 tests covering: registration validation (valid/invalid emails), password strength (weak/strong), duplicate email prevention, password hashing (bcrypt verification), login validation (correct/wrong password, nonexistent email), single-session enforcement (second login invalidates first, only one active session), rate limiting logic (5 allowed, 6th rate-limited, time-window reset via `freezegun` mocking)
- Fixtures: `auth_service`, `user_repo`, `test_db`, `test_user_data_in_db`
- Uses `monkeypatch` to patch `datetime` in `src.models.login_attempt` and `src.repositories.login_attempt_repository` for rate-limit time manipulation

### Integration tests (`backend/tests/integration/test_auth_endpoints.py:1-541`):
- 15+ tests covering: registration endpoint (success, invalid email, weak password, duplicate email, missing fields, error envelopes), login after registration, contract compliance (response schema + error envelope), single-session concurrency (2 simultaneous logins → exactly 1 active session), session persistence (login sets cookies), rate limiting integration (5×401 then 429), cookie refresh on authenticated request (T050A stub: `pass`), logout (204 + cookie clear + session invalidated), logout error case (401 without session), post-logout access denied (401 on `/auth/me`)
- Uses `test_client` (httpx AsyncClient with `test_db` fixture and overridden `get_db` dependency) and `test_user_data_in_db` fixture

### Contract tests (`backend/tests/contract/test_auth_api.py:1-128`):
- 4 tests verifying: login success response schema (`{user_id, email}`, no `session_id`/`created_at`), login invalid credentials error envelope (`{detail, status_code, error_code}`), login rate-limited error envelope (429 + `rate_limited`), login missing fields return 422

**Test health**:
- All tests are TDD-written with clear acceptance criteria matching spec.md acceptance scenarios
- Mocked dependencies: `freezegun` for rate-limit time manipulation
- Integration tests use `test_client` + `test_db` fixtures (from `conftest.py`)
- Rate limiting tests patch `datetime` in both `src.models.login_attempt` and `src.repositories.login_attempt_repository` — demonstrates awareness of testing complexity
- Gap: T050A cookie refresh test is currently a `pass` stub at `test_auth_endpoints.py:440`
- No end-to-end tests with Redis (all rate-limit tests use SQLite in-memory)
- Test coverage: 21 FRs mapped to 116 tasks (100% per `REMEDIATION_REPORT.md:130-133`)

**Evidence**: `backend/tests/unit/test_auth_service.py:1-509`, `backend/tests/integration/test_auth_endpoints.py:1-541`, `backend/tests/contract/test_auth_api.py:1-128`, `backend/tests/conftest.py:1-162`

---

## 8. CI/CD, Docker, and deployment

**CI/CD pipeline**: **Not implemented**. No `.github/workflows/` directory, no GitLab CI, no CircleCI config found in repository.

**Local development workflow**:
- Backend: `cd backend && pytest tests/` — runs unit, integration, and contract tests
- Frontend: `cd frontend && npm test` — runs Jest tests; `npm run lint` — ESLint; `npm run format` / `npm run format:check` — Prettier
- MyPy type checking configured in `pyproject.toml:83-87` but no typecheck script in frontend `package.json`

**Docker/Deployment**:
- **No Dockerfile or `docker-compose.yml`** found in repository
- Roadmap (`CLAUDE.md:341-355`, `CLAUDE.md:357-367`) mentions Docker Compose for local multi-service development and production deployment to AWS ECS/Vercel, but not implemented
- Backend dependencies (from `pyproject.toml:15-26`): `fastapi==0.104.1`, `uvicorn[standard]==0.24.0`, `sqlalchemy==2.0.23`, `alembic==1.12.1`, `asyncpg==0.29.0`, `bcrypt==4.1.1`, `pydantic==2.5.0`, `pydantic-settings==2.1.0`, `python-dotenv==1.0.0`, `httpx==0.25.2`
- Frontend dependencies (from `package.json:17-41`): `next^14.0.0`, `react^18.2.0`, `react-dom^18.2.0`, `typescript^5.3.0`

**Environment configuration**:
- `.env.example` files exist for both backend and frontend (but no committed `.env` files)
- Key env vars: `DATABASE_URL`, `SECRET_KEY`, `DEBUG`, `DATABASE_ECHO`, `EMAIL_PROVIDER`, `EMAIL_FROM`, `REDIS_URL`, `CORS_ORIGINS`, `LOG_LEVEL`
- Per `CLAUDE.md:204-205`: "Never commit: API keys, database passwords, JWT signing secrets... Use environment variables or a proper secrets mechanism."

**Evidence**: `backend/pyproject.toml:15-26`, `frontend/package.json:17-41`, `backend/.env.example`, `frontend/.env.example`, `CLAUDE.md:341-355`, `CLAUDE.md:357-367`

---

## 9. Documentation/configuration

**Root-level documentation**:
- `CLAUDE.md:1-432` — Comprehensive project instructions (19 sections): mission, roadmap, architecture, conventions, daily-development protocol, testing guidelines, security rules, database rules, FastAPI rules, Next.js rules, Redis rules, AI/RAG rules, observability, Docker/deployment, CI/CD rules, AI tool usage, roadmap alignment, simplified examples, definition of done, current priority
- `IMPLEMENTATION_SUMMARY.md:1-188` — User Story 1 (Registration) complete: 25 tests, 11 files changed, acceptance scenarios, constitution compliance, git status, next-step commands
- `PROJECT_STATUS.md:1-112` — High-level status: Phase 1C completed, verification results, constraints
- `TEST_VERIFICATION_REPORT.md:1-330` — Test verification status, environment issues preventing automated test execution

**Specs directory** (`specs/001-user-auth-foundation/`):
- `spec.md:1-174` — Core feature specification with 5 user stories, edge cases, requirements
- `plan.md:1-115` — Implementation plan (now `in_review` awaiting board acceptance)
- `tasks.md:T001-T115+` — Task tracking with 116 tasks + T019A
- `requirements.md:1-21` — Requirements checklist mapping FRs to SCs
- `contracts/auth-api.md:1-325` — Full API contract: endpoints, request/response models, error envelopes, cookie formats, testing scenarios
- `contracts/user-api.md:1-276` — User profile + password change API contract
- `data-model.md:1-400` — Entity definitions (User, Session, LoginAttempt), constraints, SQL schema, migration strategy, testing data, retention policies
- `quickstart.md:1-622` — Runnable validation scenarios for register→login→logout, authorization boundaries, password validation, rate limiting, session timeout, password change
- `US1_IMPLEMENTATION_REPORT.md` — User Story 1 implementation status
- `FOUNDATION_IMPLEMENTATION_REPORT.md` — Foundation implementation status
- `REMEDIATION_REPORT.md:1-163` — 8 remediation recommendations verified as applied (session timeout wording, CSRF tests, cookie flags, rate limiting, registration UX, email service out of V1, account deletion out of scope)
- `COOKIE_REFRESH_CONSISTENCY_REPORT.md:1-196` — Cookie refresh & session timeout consistency analysis (problem/solution, changes applied, cross-artifact alignment, test additions)

**Configuration files**:
- `backend/pyproject.toml` — Project deps, black/ruff/mypy settings, pytest options
- `frontend/package.json` + `package-lock.json` — Node deps, scripts
- `frontend/tsconfig.json` — TypeScript paths `@/* → src/*`
- `frontend/jest.config.js` — `ts-jest`, `jsdom` env, `@/* → src/*` mapping
- `frontend/.eslintrc.json` — Extends `next/core-web-vitals`, rules for React, console, HTML links
- `frontend/.prettierrc` — Semi, singleQuote, tabWidth 2, printWidth 100
- `frontend/tailwind.config.js` — Content paths, empty theme extend
- `backend/.python-linters.toml` — Linter configuration
- `backend/.env.example` — All environment variables with defaults
- `frontend/.env.example` — Next.js API URL + debug flag

**Evidence**: `CLAUDE.md`, `IMPLEMENTATION_SUMMARY.md`, `PROJECT_STATUS.md`, `TEST_VERIFICATION_REPORT.md`, `specs/001-user-auth-foundation/`

---

## 10. Technical risks and gaps (reclassified)

### Confirmed current blocker (actively blocks progress):

1. **No CI/CD pipeline** — No automated testing on PRs, no code quality enforcement, no deployment automation. Merges happen via local `pytest` and `npm test` only. *(Evidence: section 8, no `.github/workflows/`)*
2. **In-memory rate limiter doesn't scale** — `rate_limiter.py` uses `defaultdict` in process memory. Multiple backend instances have independent counters. `redis_url` config exists but is unused (`Optional[str] = None`). *(Evidence: section 5, rate_limiter.py:10-22)*
3. **No Docker containerization** — Cannot be deployed as containerized service. Roadmap mentions ECS/Vercel but no Docker files exist. Local development requires manual database and service setup. *(Evidence: section 8, no Dockerfile or docker-compose.yml)*
4. **Weak default SECRET_KEY** — `SECRET_KEY` defaults to `"dev-secret-key-change-in-production"` in `config.py:19`. Would need explicit env var override for production. *(Evidence: section 5, config.py:19)*
5. **CORS restricted to localhost** — `cors_origins` only allows `http://localhost:3000` and `http://localhost:8000`. Would need updating for production domains. *(Evidence: section 5, config.py:42-45)*
6. **Cookie refresh middleware integration unproven** — `session_refresh.py` exists and is registered in `main.py:50`, but T050A test is a stub. Need end-to-end verification that cookie Max-Age is refreshed on every authenticated response. *(Evidence: section 5, session_refresh.py:1-64, test_auth_endpoints.py:433-440)*

### Production-readiness gap (needed for production but not immediately blocking):

7. **No database migration verification** — Alembic configured with 2 migrations but no migrations generated/run against real database. `migrations/` directory inspected but no `pg`-backed migration test. *(Evidence: section 4, migrations/versions/001/002 exist but untested against PostgreSQL)*
8. **CSRF token manager is in-memory global** — `CSRFTokenManager` tokens lost on restart. Not all state-changing endpoints validate CSRF (only `/users/password` does; `/auth/register`, `/auth/login`, `/auth/logout` rely on `SameSite=Strict`). *(Evidence: section 5, csrf.py:83, user_routes.py:45-79)*
9. **No HTTPS enforcement at server level** — Code sets `Secure` flag on cookies but no guaranteed HTTPS termination. *(Evidence: section 5, config.py references Secure flag but no server config)*
10. **Session refresh middleware logic unverified** — Middleware `setdefault("Set-Cookie", ...)` only sets if not already set (line 57). Could miss refresh if response already has Set-Cookie. No test verifies the refreshing behavior. *(Evidence: section 5, session_refresh.py:57)*

### Recommended improvement (nice-to-have, long-term value):

11. **No absolute expiration cap ambiguity** — Spec.md assumptions L173 and SC-012 clarify "30 days of rolling inactivity; no absolute expiration cap", but the original cookie spec used fixed `Max-Age=2592000` (30 days from login). The cookie refresh middleware was added to resolve this, but integration is unverified. *(Evidence: section 5, config.py:24, session_validator.py:58-63)*
12. **CSRF validation on all state-changing endpoints as defense-in-depth** — `/auth/register`, `/auth/login`, `/auth/logout` currently rely on `SameSite=Strict` only. Adding `X-CSRF-Token` validation would be defense-in-depth since no actual CSRF vulnerability has been demonstrated in the repository (SameSite=Strict provides partial protection). *(Evidence: section 5, auth_routes.py:69-150, user_routes.py:45-79)*
13. **Rate limit headers on 429 responses** — Add `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` to 429 responses for better client awareness. *(Evidence: section 5, rate_limiter.py:10-46)*
14. **Production CORS configuration** — Update `cors_origins` for production domains once deployed. *(Evidence: section 5, config.py:42-45)*
15. **Observability foundations** — Structured logs, request IDs, basic metrics. *(Evidence: CLAUDE.md:367-375, no current implementation)*

---

## 11. Top 5 engineering priorities (evidence-based with dependencies)

### Priority 1: Set up PostgreSQL database + Alembic migrations ✅ *Partially exists*
- **Evidence**: Models (`backend/src/models/user.py`, `backend/src/models/session.py`) and migrations (`migrations/versions/001_create_users_sessions_tables.py`, `002_add_session_csrf_token.py`) already exist
- **Action**: Create PostgreSQL instance, run `alembic upgrade head` to create users, sessions, login_attempts tables. This is the single source of truth for the data model.
- **Dependency**: Blocked by — nothing else can proceed without a live database. All subsequent priorities depend on this being verified first.
- **Reclassification**: Production-readiness gap → Confirmed current blocker (per user request #3, distinguish missing execution from existing models/migrations)

### Priority 2: Replace weak default SECRET_KEY + configure Redis for rate limiter ✅
- **Evidence**: `config.py:19` has `secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")`
- **Action**: Remove default from `config.py:19`; make `SECRET_KEY` a required env var. Add Redis backend to `rate_limiter.py` or add async fallback that tries Redis first, falls back to in-memory.
- **Dependency**: Depends on Priority 1 (database setup needed to verify Redis connection string format). But can be prepared in parallel with database credentials.
- **Reclassification**: Production-readiness gap (was blocker, now downgraded since it's a configuration fix, not a missing component)

### Priority 3: Implement cookie refresh middleware end-to-end verification ✅
- **Evidence**: `session_refresh.py:1-64` exists, T050A test (`test_auth_endpoints.py:433-440`) is a `pass` stub
- **Action**: Fix T050A stub test; verify `session_refresh.py` actually refreshes `Set-Cookie: Max-Age=2592000` on every authenticated request; confirm rolling inactivity window aligns with cookie lifetime (30 days).
- **Dependency**: Depends on Priority 1 (database needed for session refresh middleware's `AsyncSessionLocal`). Also depends on Priority 2 (Redis config may affect session storage).
- **Reclassification**: Confirmed current blocker (per user request #4, cookie refresh is a verified integration gap; CSRF reclassification as defense-in-depth applies separately)

### Priority 4: Add CI pipeline (GitHub Actions) ✅
- **Evidence**: No `.github/workflows/` directory exists; local workflow is `cd backend && pytest` and `cd frontend && npm test`
- **Action**: Create `.github/workflows/test.yml` running `cd backend && pytest`, `cd frontend && npm test`, `npm run lint`, `npm run format:check` on every PR. Fail fast on breakage.
- **Dependency**: Depends on Priority 1 (database needed for pytest to connect) and Priority 3 (cookie refresh test must pass locally before CI).
- **Reclassification**: Confirmed current blocker (no CI pipeline is a hard block for code quality gates on PRs)

### Priority 5: Create Dockerfile + docker-compose.yml ✅
- **Evidence**: No Dockerfile or `docker-compose.yml` exists; roadmap mentions ECS/Vercel but not implemented
- **Action**: Create Dockerfile for backend (FastAPI + uvicorn + alembic + Redis optional), Dockerfile for frontend (Next.js), and `docker-compose.yml` with services for backend, frontend, and Redis. Health checks. Environment-driven config.
- **Dependency**: Depends on Priority 1 (database URL needed for Docker config), Priority 2 (Redis connection string), Priority 4 (CI pipeline can run inside Docker).
- **Reclassification**: Production-readiness gap (deployment blocker, but depends on having the database and Redis configured first)

**Rationale**: These 5 priorities address the most critical blocks — without a database (Priority 1), nothing else works. Without cookie refresh verification (Priority 3), session timeout is ambiguous. Without CI (Priority 4), code quality degrades on every merge. Without SECRET_KEY fix (Priority 2) and Docker (Priority 5), production deployment is unsafe and manual.

---

## 12. Proposed engineering strategy (3-phase, evidence-based with dependencies)

**Strategy: TDD-focused incremental delivery with security-by-default gates.**

### Phase 1 — Foundation & Safety (Weeks 1-2)

**Objective**: Establish the data foundation and security baseline.

1. **Set up PostgreSQL + Alembic** (Priority 1) — Create DB, run `001_create_users_sessions_tables.py`. Verify tables exist and models can create/read records. *Depends on: nothing (infrastructure setup).*

2. **Fix SECRET_KEY + add Redis fallback** (Priority 2) — Remove default from `config.py:19`; add Redis-backed RateLimiter fallback. Update `rate_limiter.py` to try Redis first, fall back to in-memory. *Depends on: Priority 1 (database credentials verified).*

3. **Add CI pipeline** (Priority 4) — Create `.github/workflows/test.yml` running backend `pytest`, frontend `npm test`, `npm run lint`, `npm run format:check`. Fail fast on breakage. *Depends on: Priority 1 (database for pytest), Priority 2 (SECRET_KEY env var format confirmed).*

4. **Security gates for merges** — Block merges if: weak passwords accepted, rate limit not enforced, secure cookie flags missing, cross-user access not returning 403. *Depends on: Priorities 1-3 (database, SECRET_KEY, CI pipeline all operational).*

### Phase 2 — Authentication Harden (Weeks 3-5)

**Objective**: Harden auth flow and verify security integrations.

5. **Cookie refresh integration** (Priority 3) — Fix `session_refresh.py`; verify T050A passes; confirm cookie Max-Age refresh on every authenticated request aligns with rolling 30-day inactivity window. *Depends on: Priorities 1-2 (database, SECRET_KEY configured).*

6. **CSRF validation as defense-in-depth** — Add CSRF token validation to `/auth/register`, `/auth/login`, `/auth/logout` endpoints. Note: Current `SameSite=Strict` provides partial CSRF protection; adding explicit CSRF token validation is defense-in-depth per reclassification in Section 10 item 12. *Depends on: Priority 1 (database for session csrf_token storage).*

7. **Session timeout tests** — Implement T097-T099 (30-day inactivity expiration) and T050A + T099A (cookie refresh beyond 30 days with continuous activity). *Depends on: Priority 3 (cookie refresh verified).*

8. **Rate limit headers** — Add `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` to 429 responses. *Depends on: Priority 1 (database + rate limiter operational).*

### Phase 3 — Deployment & Observability (Weeks 6-8)

**Objective**: Containerize, automate, and prepare for production.

9. **Dockerfile + docker-compose.yml** (Priority 5) — Backend (FastAPI + uvicorn + alembic + Redis optional), Frontend (Next.js), Redis service. Health checks. Environment-driven config. *Depends on: Priorities 1-4 (database, SECRET_KEY, CI, cookie refresh all verified).*

10. **Configure production CORS** — Update `cors_origins` for production domains. *Depends on: Priority 1 (database configured, deployment context established).*

11. **Health check + readiness probe** — Add `/health` (simple) and `/readiness` (DB connectivity) endpoints with proper completion. *Depends on: Priority 1 (database).*

12. **Observability foundations** — Structured logs, request IDs, basic metrics. *Depends on: Priority 4 (CI pipeline running in production-like environment).*

### Key engineering principles (per `CLAUDE.md`):

- **TDD**: Every new feature must have tests written before/alongside implementation. 100% requirements coverage (21 FRs → 116 tasks).
- **Security by default**: bcrypt hashing, httpOnly/Secure/SameSite=Strict cookies, rate limiting, CSRF validation, parameterized SQL queries, generic error messages.
- **No secrets in code**: All secrets via environment variables; never commit `.env` files.
- **Small, reversible commits**: Each commit should be a single logical change with a clear intent.
- **Interview-defensible code**: Every implementation should be interview-ready with explanation of design decisions.
- **Roadmap alignment**: Features introduced in the roadmap's learning order; don't build whole final architecture on Day 1.

### Delegation model (per CEO AGENTS.md):

- **CTO**: Code, bugs, features, infra, devtools — priorities 1-5 from Phase 1-3
- **CMO**: Marketing, content, devrel as needed for launch/awareness
- **UXDesigner**: UX, design, user research for frontend flows (registration, login, dashboard)

---

## Summary of all 12 assessment areas

| # | Area | Key Finding |
|---|---|---|
| 1 | Repository/Git state | `main` branch, 99 modified files (including 13 `.claude`, 10 `.harness`, 14 `.specify` agent files + 40 backend + 50 frontend + 7 root/project files), 2 untracked (`.freebuff/`, `plan.md`); no `.env` committed; no Docker/CI |
| 2 | Frontend architecture | Next.js 14 + React 18 + TS + Tailwind 4; BFF patterns; API client with cookie auth |
| 3 | Backend architecture | FastAPI + SQLAlchemy 2 + asyncpg + Alembic; layered: routes → services → repos → models |
| 4 | Database architecture | PostgreSQL; users/sessions/login_attempts tables; Alembic migrations 001/002; critical indexes |
| 5 | Auth & security | bcrypt 12-round hashing, secure cookies, rate limiting, CSRF on password change only, generic errors — but in-memory rate limiter, no Redis, weak default SECRET_KEY, CORS localhost-only, unverified cookie refresh, CSRF not on auth endpoints |
| 6 | API architecture | `/api/v1/auth/` + `/api/v1/users/` endpoints; Pydantic models; error envelope `{detail, status_code, error_code}`; Set-Cookie headers |
| 7 | Tests & test health | 25+ tests across 3 layers (unit: 12, integration: 15+, contract: 4); T050A stub; 100% FR coverage (21→116) |
| 8 | CI/CD, Docker, deployment | None implemented; local: `pytest` + `npm test`; roadmap mentions ECS/Vercel/Docker but not built |
| 9 | Documentation/configuration | `CLAUDE.md` (432 lines), specs/`001-user-auth-foundation/` (10+ docs), `.env.example` templates, config files |
| 10 | Technical risks/gaps | 15 reclassified: 6 confirmed current blockers (no CI/CD, in-memory rate limiter, no Docker, weak SECRET_KEY, CORS localhost, unverified cookie refresh), 4 production-readiness gaps (no migration verification, in-memory CSRF manager, no HTTPS, middleware unverified), 5 recommended improvements (no absolute cap ambiguity, CSRF as defense-in-depth, rate limit headers, production CORS, observability) |
| 11 | Top 5 priorities | 1) PostgreSQL + Alembic (execution gap), 2) SECRET_KEY + Redis, 3) Cookie refresh verification, 4) CI pipeline, 5) Dockerfile + compose |
| 12 | Engineering strategy | TDD incremental delivery with security-by-default gates; 3-phase plan over 8 weeks; CTO/CMO/UXDesigner delegation |

**Overall assessment**: The repository has a solid TDD foundation with 25+ tests covering the registration/login/logout flow, bcrypt password hashing, email validation, password strength enforcement, rate limiting, and single-session enforcement. However, critical gaps exist in scalability (in-memory rate limiter, no Redis), deployment (no Docker, no CI/CD), and security (weak default SECRET_KEY, CORS localhost-only, unverified cookie refresh middleware, CSRF not on all endpoints). The `plan.md` document is `in_review` awaiting board acceptance before implementation subtasks are delegated to CTO, CMO, and UXDesigner.

**Final disposition**: `in_review` — board must accept `plan.md` before implementation subtasks can be delegated. All findings are reclassified per user corrections: confirmed current blockers, production-readiness gaps, and recommended improvements. CSRF recommendations without evidence of actual vulnerability are classified as defense-in-depth. PostgreSQL/Alembic gap distinguished as missing production execution from existing models and migrations. 99 modified files clarified: pre-existing working-tree state including agent/infrastructure files plus application code, no changes created during assessment.