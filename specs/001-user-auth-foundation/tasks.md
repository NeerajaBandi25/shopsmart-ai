# Tasks: User Authentication and Account Foundation

**Input**: Design documents from `/specs/001-user-auth-foundation/`

**Prerequisites**: plan.md (tech stack, project structure), spec.md (5 user stories P1/P2), data-model.md (entities, concurrency), contracts/ (API endpoints), quickstart.md (validation scenarios)

**Tests**: REQUIRED per Constitution Principle IV (Test-Driven Quality). Tests are part of implementation, not optional. Includes unit, integration/API, negative, authorization, session-expiration, rate-limit, password-change, and concurrency tests.

**Organization**: Tasks grouped by user story (US1-US5) to enable independent implementation and testing. Tests written first (TDD), verified to FAIL before implementation begins.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US5) - omitted for Setup/Foundational/Polish phases
- File paths included for each task

## Path Conventions

- **Backend**: `backend/src/` (FastAPI)
- **Frontend**: `frontend/src/` (Next.js)
- **Migrations**: `backend/migrations/alembic/versions/`
- **Tests**: `backend/tests/{unit,integration}`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency configuration

- [ ] T001 Create project directory structure: `backend/src/{core,models,repositories,services,api}`, `backend/tests/{unit,integration,fixtures}`, `frontend/src/{app,components,lib,types}`, `frontend/tests/`
- [ ] T002 Initialize Python project: create `backend/pyproject.toml` or `requirements.txt` with FastAPI, SQLAlchemy, bcrypt, asyncpg, pytest, pytest-asyncio, httpx (for testing)
- [ ] T003 [P] Initialize Next.js frontend: create `frontend/package.json` with TypeScript, React Hook Form, jest, @testing-library/react
- [ ] T004 [P] Configure Python linting and formatting: ruff, black, isort in `backend/`
- [ ] T005 [P] Configure TypeScript/linting: ESLint, Prettier in `frontend/`
- [ ] T006 Configure database connection: `backend/src/core/config.py` with DATABASE_URL from environment variables
- [ ] T007 Initialize Alembic for migrations: `alembic init backend/migrations`
- [ ] T008 Create pytest fixtures: `backend/tests/conftest.py` with db session, client, test users, mocked email provider

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure MUST complete before ANY user story implementation

**CRITICAL**: No user story work can begin until this phase completes

### Database & Models Setup

- [ ] T009 Create database connection factory: `backend/src/database.py` with SQLAlchemy engine, session factory, async support via asyncpg
- [ ] T010 Create base model class: `backend/src/models/base.py` with common fields (id UUID, created_at, updated_at)
- [ ] T011 [P] Create User entity model: `backend/src/models/user.py`
  - Fields per data-model.md: id (UUID PK), email (VARCHAR 255, UNIQUE, NOT NULL, CHECK email format), password_hash (VARCHAR 255, NOT NULL), created_at (TIMESTAMP NOT NULL DEFAULT NOW), updated_at (TIMESTAMP NOT NULL DEFAULT NOW)
- [ ] T012 [P] Create Session entity model: `backend/src/models/session.py`
  - Fields per data-model.md: id (UUID PK), user_id (UUID FK to users, NOT NULL), created_at (TIMESTAMP NOT NULL DEFAULT NOW), last_activity (TIMESTAMP NOT NULL DEFAULT NOW), ip_address (INET NOT NULL), user_agent (VARCHAR 500 NOT NULL), is_active (BOOLEAN NOT NULL DEFAULT TRUE)
  - **Session Timeout (Rolling Inactivity Only)**: Session expires only when NOW() - last_activity > 30 days. There is NO absolute expiration cap. On each authenticated request, last_activity is updated, extending the timeout to last_activity + 30 days. Sessions remain valid indefinitely while the user is active.
- [ ] T013 [P] Create LoginAttempt entity model: `backend/src/models/login_attempt.py`
  - Fields per data-model.md: id (UUID PK), email (VARCHAR 255 NOT NULL), ip_address (INET NOT NULL), attempted_at (TIMESTAMP NOT NULL DEFAULT NOW), success (BOOLEAN NOT NULL), failure_reason (VARCHAR 100, CHECK constraint: success=TRUE ⟹ failure_reason IS NULL AND success=FALSE ⟹ failure_reason IS NOT NULL)
- [ ] T014 Create initial database migration: `backend/migrations/alembic/versions/001_create_users_sessions_tables.py`
  - Tables: users (with indexes on email, created_at), sessions (with indexes on user_id+is_active, expires_at), login_attempts (with indexes on ip_address+attempted_at, attempted_at)

### Email Service Foundation

- [ ] T015 Create email provider abstraction: `backend/src/core/email_provider.py` (Correction #2: Email service per spec clarification)
  - Abstract base class `EmailProvider` with method `send_notification(recipient: str, subject: str, body: str) -> bool`
  - Returns bool (success/failure); raises no exceptions; logs failures internally
  - Rationale per spec clarification: Email delivery is best-effort, non-blocking; account creation succeeds regardless
  - Email is used ONLY for optional notifications (password reset, security alerts - future); NOT required for v1 core registration/login
- [ ] T016 [P] Create mock email provider for testing: `backend/src/core/email_provider_mock.py`
  - Implements EmailProvider; stores emails in in-memory log for test verification
  - `get_sent_emails() -> list` for test assertions (verify email was/wasn't sent)
  - Default provider in tests; never calls external service
- [ ] T017 [P] Create production email provider stub: `backend/src/core/email_provider_prod.py`
  - Stub implementation: logs "would send email to {recipient}" but does not call any service
  - Ready for integration with SendGrid/AWS SES/etc. in future sprints
  - Email delivery is out of scope for v1; stub allows infrastructure readiness

### Security & Authentication Foundations

- [ ] T018 Create password hashing module: `backend/src/core/security.py`
  - Function `hash_password(password: str) -> str` using bcrypt with 12 salt rounds
  - Function `verify_password(plain: str, hashed: str) -> bool` for password verification
  - Function `generate_session_id() -> str` for cryptographically random UUID session tokens
- [ ] T019 Create CSRF protection module: `backend/src/core/csrf.py`
  - CSRF token generation and validation (double-submit cookie pattern with SameSite=Strict)
- [ ] T019A Create CSRF behavioral tests: `backend/tests/integration/test_auth_endpoints.py`
  - Test state-changing request without valid CSRF token → verify 400 Bad Request or 403 Forbidden response
  - Test state-changing request with valid CSRF token → verify 204 or 200 success
  - Test CSRF token generation (create token, verify format/entropy)
  - Test CSRF token validation (expired token rejected, tampered token rejected)
  - Per FR-014 (CSRF protection required) and SC-010 (CSRF tokens prevent forgery attacks)
- [ ] T020 Create session validation logic: `backend/src/core/session_validator.py` (Correction #3: Session expiration clarity)
  - Function `validate_session(session_id: str) -> dict` returning user_id and refresh_cookie=True if valid, None if expired/invalid
  - Session expiration logic (Rolling Inactivity Only, NO absolute cap):
    - Fetch session from database
    - If session.is_active = FALSE: return None (logged out)
    - If NOW() - session.last_activity > 30 days (2592000 seconds): return None (inactivity timeout)
    - If user not found: return None
    - Otherwise: UPDATE session SET last_activity = NOW() and return user_id with refresh_cookie=True flag
  - Caller (dependency injection layer) will refresh session cookie Max-Age=2592000 on every authenticated request
  - This ensures: 30-day rolling inactivity window (last_activity), any request extends timeout indefinitely
  - Cookie lifetime on client side mirrors server-side rolling inactivity (both refreshed together)
  - No absolute expiration cap: sessions remain valid while user is active
  - Testable: fixed times can be mocked; inactivity condition independently verified

### API & Middleware Infrastructure

- [ ] T021 Create FastAPI app initialization: `backend/src/main.py`
  - FastAPI instance, middleware setup (CORS, logging), exception handlers (return generic errors, no stack traces)
  - CORS configuration per Correction #4 (NextJS/FastAPI architecture): Allow frontend origin with credentials=True
- [ ] T022 Create API error responses: `backend/src/core/exceptions.py`
  - Custom exception classes: ValidationError, AuthenticationError, AuthorizationError, RateLimitError
  - Error response envelope: {detail, status_code, error_code}
- [ ] T023 Create dependency injection: `backend/src/api/v1/deps.py`
  - `get_db()` dependency for database session
  - `get_current_user()` dependency for authenticated user extraction from session cookie
    - Calls `validate_session()` to check inactivity and get user_id
    - If valid and refresh_cookie=True: Injects a response header or context to signal caller to refresh session cookie with Set-Cookie Max-Age=2592000
    - Per Correction #4: Extract session_id from secure httpOnly cookie (browser sends automatically for same-origin)
  - Per Correction #4: Cookie refresh happens at middleware/response layer (after successful request completion)
- [ ] T024 Create rate limiting module: `backend/src/core/rate_limiter.py`
  - Function `check_login_rate_limit(ip_address: str) -> bool` (max 5 failed attempts per 15 minutes)
  - Use Redis if available, fall back to in-memory

### Data Access Layer (Repositories)

- [ ] T025 Create User repository: `backend/src/repositories/user_repository.py`
  - Methods: `create_user(email: str, password_hash: str) -> User`, `get_user_by_email(email: str) -> User`, `get_user_by_id(id: UUID) -> User`, `user_exists(email: str) -> bool`
  - All using parameterized queries (SQLAlchemy ORM)
- [ ] T026 Create Session repository: `backend/src/repositories/session_repository.py`
  - Methods: `create_session(user_id: UUID, ...) -> Session`, `get_session(session_id: str) -> Session`, `update_session_activity(session_id: str)`, `invalidate_session(session_id: str)`, `invalidate_user_sessions(user_id: UUID)`, `get_active_session(user_id: UUID) -> Session`
- [ ] T027 Create LoginAttempt repository: `backend/src/repositories/login_attempt_repository.py`
  - Methods: `log_attempt(email: str, ip: str, success: bool, reason: str)`, `count_failed_attempts(ip: str, minutes: int) -> int`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - New User Registration (Priority: P1) 🎯 MVP

**Goal**: Allow new users to create accounts with email/password, validate inputs, hash passwords securely, prevent duplicates

**Independent Test**: Navigate to registration form → enter valid email + strong password → submit → verify account exists in database and user can log in with those credentials

### Tests for User Story 1 (TDD - write FIRST, verify FAIL before implementation)

**Unit Tests: `backend/tests/unit/test_auth_service.py`**

- [ ] T028 [P] [US1] Test registration validation: email format validation per RFC 5322, reject invalid formats
- [ ] T029 [P] [US1] Test password strength enforcement: minimum 8 characters, require uppercase, lowercase, digit, special character; reject weak passwords
- [ ] T030 [P] [US1] Test duplicate email prevention: second registration with same email returns ConflictError (409)
- [ ] T031 [P] [US1] Test password hashing: registered password is hashed with bcrypt, never stored plaintext; `verify_password()` returns True for correct password, False for incorrect

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py`**

- [ ] T032 [P] [US1] Test registration endpoint: POST /api/v1/auth/register with valid email/password returns 201 with user_id, email, created_at; User record exists in database; frontend displays "Account created successfully — please log in" and redirects to /auth/login
- [ ] T033 [P] [US1] Test registration error cases: invalid email returns 400, weak password returns 400, duplicate email returns 409, validation errors include error_code field
- [ ] T034 [P] [US1] Test immediate login after registration: registered user can log in with provided credentials and receive session

**Contract Tests: `backend/tests/contract/test_auth_api.py`**

- [ ] T035 [P] [US1] Verify registration endpoint contract per contracts/auth-api.md: POST /api/v1/auth/register accepts {email, password}, returns {user_id, email, created_at} or error envelope

### Implementation for User Story 1

- [ ] T036 Create User registration service: `backend/src/services/auth_service.py`
  - Method `register_user(email: str, password: str) -> dict`
  - Validates email format (RFC 5322 compliant), password strength (≥8 chars, uppercase, lowercase, digit, special char)
  - Checks for duplicate email (email uniqueness)
  - Hash password with bcrypt (12 rounds), create User record
  - Returns user_id, email, created_at
  - Raises ValidationError (400), ConflictError (409)
  - Per FR-001, FR-002, FR-003, FR-004
- [ ] T037 Create registration endpoint: `backend/src/api/v1/auth_routes.py`
  - `POST /api/v1/auth/register` → { email, password } → { user_id, email, created_at } (201) or error (400/409)
  - Input validation via Pydantic models
  - HTTPS required (enforced at deployment)
  - Per FR-001, FR-002, FR-003, FR-004
- [ ] T038 [P] Create registration form component: `frontend/src/components/registration-form.tsx`
  - Email input (with validation display)
  - Password input (with strength indicator per FR-003: ≥8 chars, uppercase, lowercase, digit, special char)
  - Submit button, error/success messages
  - Client-side validation matches backend (email format, password strength)
- [ ] T039 [P] Create registration page: `frontend/src/app/auth/register/page.tsx`
  - Route: /auth/register (public, no auth required)
  - Renders RegistrationForm component
  - On success: Navigate to /auth/login with message "Account created successfully"
- [ ] T040 [P] Create API client for registration: `frontend/src/lib/api-client.ts`
  - Function `register(email: string, password: string)` calls POST /api/v1/auth/register
  - Handles errors, returns response or throws
  - Per Correction #4: Use credentials: 'include' for cross-site cookie handling
- [ ] T041 Add logging for registration: `backend/src/services/auth_service.py`
  - Log registration attempts (success/failure) with email (not password), timestamp
  - Log validation errors (weak password, invalid email, duplicate email)

**Checkpoint**: User Story 1 complete - new users can register with validated email/password

---

## Phase 4: User Story 2 - Existing User Login (Priority: P1)

**Goal**: Allow registered users to log in, establish secure server-side sessions, set httpOnly cookies, enforce single-session per user with database locking, handle rate limiting

**Independent Test**: Log in with correct email + password → verify session cookie set → verify GET /auth/me returns user → verify access to protected pages works → log in from another device to verify single-session enforcement (previous session invalidated)

### Tests for User Story 2 (TDD - write FIRST, verify FAIL before implementation)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [ ] T042 [P] [US2] Test login validation: correct password succeeds, incorrect password fails, non-existent email fails, generic "invalid credentials" error (no email existence hints)
- [ ] T043 [P] [US2] Test single-session enforcement: second login from different device invalidates previous session; only one active session per user
- [ ] T044 [P] [US2] Test rate limiting logic: 5 failed attempts allowed, 6th attempt rate-limited, rate limit resets after 15 minutes

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [ ] T045 [P] [US2] Test login endpoint: POST /api/v1/auth/login with correct email/password returns 200 with {user_id, email} and Set-Cookie header with httpOnly, Secure, SameSite=Strict, Max-Age=2592000
  - Verify Set-Cookie header includes ALL security flags: httpOnly (no JavaScript access), Secure (HTTPS only), SameSite=Strict (cross-site protection), Max-Age=2592000 (30 days)
  - Add negative test: Verify failure if any flag is missing
  - Verify cookie is opaque session_id (no user info exposed)
- [ ] T046 [P] [US2] Test login error cases: invalid password returns 401, non-existent email returns 401, rate limiting returns 429, all errors use generic message
- [ ] T047 [P] [US2] Test session cookie behavior: Set-Cookie header present, cookie contains session_id (opaque, no user info)
- [ ] T048 [US2] Test single-session concurrency: simultaneous login attempts from two devices; verify only final login active session exists, previous is invalidated (tests database FOR UPDATE locking)
- [ ] T049 [US2] Test session persistence: log in → close browser → reopen → GET /auth/me succeeds (session persists across browser restarts via cookie)
- [ ] T050 [US2] Test rate limiting integration: make 6 failed login attempts from same IP; verify 429 response on 6th; wait/clear rate limit; verify login works again
- [ ] T050A [US2] Test cookie refresh on authenticated request: log in with Max-Age=2592000 → advance clock 10 days → make authenticated request (GET /auth/me) → verify Set-Cookie response refreshes Max-Age to new 2592000 (30 days from current time) → session remains valid far beyond 30 calendar days because both server last_activity and cookie lifetime are continuously refreshed

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [ ] T051 [P] [US2] Verify login endpoint contract: POST /api/v1/auth/login accepts {email, password}, returns {user_id, email} (200) with Set-Cookie, or error (401/429)

### Implementation for User Story 2

- [ ] T052 Create login service with single-session enforcement: `backend/src/services/auth_service.py` (extend)
  - Method `login_user(email: str, password: str, ip_address: str, user_agent: str) -> dict`
  - Transaction (READ COMMITTED isolation per data-model.md):
    1. Check rate limit first: if >5 failed attempts from IP in last 15 min → raise RateLimitError (429)
    2. SELECT user BY email; if not found or password wrong (bcrypt verify fails) → log LoginAttempt(success=FALSE, reason) → raise AuthenticationError (401)
    3. SELECT user FOR UPDATE (row-level lock on user row, prevents concurrent session race)
    4. Invalidate existing active session if present: UPDATE sessions SET is_active=FALSE WHERE user_id=? AND is_active=TRUE
    5. INSERT new Session with is_active=TRUE, last_activity=now, ip_address, user_agent (no absolute expiration date; inactivity timeout managed at validation time)
    6. COMMIT transaction (lock released)
    7. Log LoginAttempt(success=TRUE)
  - Returns session_id, user_id, email (session_id in cookie only, never in response body)
  - Raises AuthenticationError (401), RateLimitError (429)
  - Per FR-005, FR-006, FR-007, FR-019, FR-020, data-model.md (single-session with FOR UPDATE)
- [ ] T053 Create login endpoint: `backend/src/api/v1/auth_routes.py` (extend)
  - `POST /api/v1/auth/login` → { email, password } → { user_id, email } (200) + Set-Cookie header (401/429 on error)
  - Extracts client IP (from X-Forwarded-For or REMOTE_ADDR)
  - Sets session cookie: httpOnly, Secure, SameSite=Strict, Max-Age=2592000 (30 days), Path=/
  - Per FR-019 (rate limiting), FR-020 (secure cookie flags), data-model.md (concurrency)
- [ ] T053A Create authenticated response middleware: `backend/src/middleware/session_refresh.py`
  - Middleware/decorator that runs after successful authenticated request
  - If `get_current_user()` returned refresh_cookie=True: respond with Set-Cookie header refreshing session cookie Max-Age=2592000
  - Ensures cookie lifetime is continuously refreshed on every authenticated request, maintaining rolling inactivity window
  - Per FR-020 (refresh cookie on activity) and SC-012 (rolling inactivity with cookie refresh)
- [ ] T054 [P] Create login form component: `frontend/src/components/login-form.tsx`
  - Email and password inputs
  - Submit button, error display (generic "invalid credentials" per FR-013 acceptance scenario)
  - Submission sends POST to /api/v1/auth/login
- [ ] T055 [P] Create login page: `frontend/src/app/auth/login/page.tsx`
  - Route: /auth/login (public, no auth required)
  - Renders LoginForm
  - On 401/429 error: Display error message (rate limiting message for 429)
  - On success: Redirect to authenticated home (e.g., /dashboard or /orders)
- [ ] T056 [P] Create session cookie handler (Correction #4): `frontend/src/lib/api-client.ts` (extend)
  - Configure fetch/axios with credentials: 'include' (browser sends session cookie automatically for same-origin)
  - Per Correction #4 (Next.js/FastAPI architecture): Session cookie sent automatically by browser for same-origin requests; no manual cookie handling needed
  - On 401 response from any endpoint: Redirect to /auth/login
- [ ] T057 Create session middleware (Next.js) (Correction #4): `frontend/middleware.ts`
  - Route protection: Redirect unauthenticated users to /auth/login when accessing protected routes
  - Check session validity via GET /api/v1/auth/me on initial app load (optional optimization: check cookie presence first)
  - Per Correction #4: Configure CORS in FastAPI to allow frontend origin with credentials=True; middleware validates session server-side
  - Per FR-006, FR-013 (401 on invalid session)
- [ ] T058 Add logging for login: `backend/src/services/auth_service.py`
  - Log all login attempts (success/failure) with email (not password), IP address, timestamp
  - Log rate limit triggers

**Checkpoint**: User Story 2 complete - users can log in securely, sessions persist, single-session enforcement prevents multi-device login

---

## Phase 5: User Story 3 - User Logout (Priority: P1)

**Goal**: Allow users to terminate their session, clear cookies, verify access denied after logout

**Independent Test**: Log in → log out → verify session terminated (GET /auth/me returns 401) → verify protected routes redirect to login

### Tests for User Story 3 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [ ] T059 [P] [US3] Test logout invalidation: session is_active set to FALSE; subsequent session lookup fails

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [ ] T060 [US3] Test logout endpoint: POST /api/v1/auth/logout with valid session returns 204 No Content + Set-Cookie with Max-Age=0; session invalidated in database
- [ ] T061 [US3] Test logout error case: POST /api/v1/auth/logout without session returns 401 Unauthorized
- [ ] T062 [US3] Test post-logout access denied: after logout, GET /auth/me returns 401; protected routes redirect to login

### Implementation for User Story 3

- [ ] T063 Create logout service: `backend/src/services/auth_service.py` (extend)
  - Method `logout_user(session_id: str)`
  - UPDATE sessions SET is_active=FALSE WHERE id=?
  - Logs logout event (success only, not failures)
  - Per FR-008, FR-009
- [ ] T064 Create logout endpoint: `backend/src/api/v1/auth_routes.py` (extend)
  - `POST /api/v1/auth/logout` → {} → 204 No Content (or 401 if session invalid)
  - Sets Set-Cookie header to clear session_id (Max-Age=0, Expires=1970-01-01)
  - Per FR-008, FR-009
- [ ] T065 Create logout button/link component: `frontend/src/components/logout-button.tsx`
  - Button triggers POST to /api/v1/auth/logout
  - On success: Redirect to /auth/login
- [ ] T066 Add logout button to navigation: `frontend/src/components/nav.tsx`
  - Visible only to authenticated users
  - Uses LogoutButton component
- [ ] T067 Update session middleware (Next.js): `frontend/middleware.ts` (extend)
  - On 401 from GET /auth/me: Clear any stale session data, redirect to /auth/login
  - Per FR-013 (401 Unauthorized)
- [ ] T068 Add logging for logout: `backend/src/services/auth_service.py`
  - Log logout event with session_id, user_id (if available), timestamp

**Checkpoint**: User Story 3 complete - users can log out, sessions invalidated, protected resources return 401

---

## Phase 6: User Story 4 - Authenticated User Identity & Authorization Boundaries (Priority: P1)

**Goal**: Correctly identify authenticated users, enforce 403 Forbidden on cross-user access, maintain identity throughout session

**Independent Test**: Log in as User A → attempt to access User B's resource (e.g., /api/users/{user-b-id}) → verify 403 response; Log in as User A → verify /api/orders returns only User A's orders; Log out → verify 401 on subsequent requests

### Tests for User Story 4 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [ ] T069 [P] [US4] Test user ownership verification: same user ID returns True, different user ID returns False
- [ ] T070 [P] [US4] Test cross-user data protection: authorization check prevents access to other user's data

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [ ] T071 [P] [US4] Test authenticated endpoint GET /auth/me: valid session returns {user_id, email, created_at} with 200; invalid session returns 401
- [ ] T072 [P] [US4] Test cross-user access denial: User A logged in attempts to access User B's profile → 403 Forbidden
- [ ] T073 [P] [US4] Test authorization boundary on user scoped endpoints: GET /api/v1/users/{user-id} returns 403 if user_id != session.user_id, 200 if owner
- [ ] T074 [US4] Test session invalidation denies access: log out → GET /auth/me returns 401 → session cleared

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [ ] T075 [P] [US4] Verify user endpoint contract per contracts/user-api.md: GET /api/v1/users/profile returns {user_id, email, created_at} (200) or 401

### Implementation for User Story 4

- [ ] T076 Create authenticated user profile endpoint: `backend/src/api/v1/auth_routes.py` (extend)
  - `GET /api/v1/auth/me` → {} → { user_id, email, created_at } (200) or 401
  - Requires valid session (validated via get_current_user dependency)
  - Per FR-010, FR-017
- [ ] T077 Create authorization decorator/middleware: `backend/src/api/v1/deps.py` (extend)
  - Decorator `require_auth()` to validate session on protected routes
  - Extract user_id from session, verify user exists
  - Inject user_id into request context
  - Per FR-010, FR-013
- [ ] T078 Create cross-user access protection helper: `backend/src/services/auth_service.py` (extend)
  - Helper `verify_user_owns_resource(user_id: UUID, resource_owner_id: UUID) -> bool`
  - Returns True if user_id == resource_owner_id, raises AuthorizationError (403) otherwise
  - Per FR-011, FR-012
- [ ] T079 Create user profile API: `backend/src/api/v1/user_routes.py` (new file)
  - `GET /api/v1/users/profile` → {} → { user_id, email, created_at } (200) or 401
  - Requires authentication via get_current_user
  - Returns only the authenticated user's own profile (implicit ownership)
  - Per FR-010, FR-011, FR-017
- [ ] T080 Add authorization checks to user routes: `backend/src/api/v1/user_routes.py` (extend)
  - Before any user-scoped operation: Call verify_user_owns_resource(current_user_id, target_user_id)
  - Return 403 if not owner
  - Per FR-011, FR-012
- [ ] T081 [P] Create authenticated user context (frontend): `frontend/src/lib/auth-context.ts` (or use React Query)
  - Store user_id, email in client state (fetch from GET /auth/me on app init)
  - Use for UI logic (e.g., hide logout button for unauthenticated users)
- [ ] T082 [P] Create authenticated dashboard page: `frontend/src/app/dashboard/page.tsx` (or /orders)
  - Protected route: Requires authentication (checked by middleware)
  - Displays current user info via GET /auth/me
  - Per FR-010, FR-017
- [ ] T083 Add authorization logging: `backend/src/api/v1/deps.py` and user_routes.py
  - Log all authorization failures (cross-user access attempts) with user_id, attempted_resource, timestamp
  - Per FR-011, FR-012

**Checkpoint**: User Story 4 complete - user identity maintained, authorization boundaries enforced (403 on cross-user access, 401 on invalid session)

---

## Phase 7: User Story 5 - Account Information Access (Priority: P2)

**Goal**: Allow users to view their profile (email, created_at), change password with current password verification, invalidate all sessions on password change

**Independent Test**: Log in → view profile (GET /api/v1/users/profile) → change password with correct current password → verify old password fails on re-login → verify new password works → verify all other sessions invalidated (forced logout on other devices)

### Tests for User Story 5 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [ ] T084 [P] [US5] Test password change validation: current password incorrect fails, new password weak fails, new password strong succeeds
- [ ] T085 [P] [US5] Test password change session invalidation: all user sessions set is_active=FALSE after password change

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [ ] T086 [P] [US5] Test password change endpoint: PUT /api/v1/users/password with correct current_password and strong new_password returns 204; old password fails on login
- [ ] T087 [P] [US5] Test password change error cases: incorrect current_password returns 400, weak new_password returns 400, invalid session returns 401
- [ ] T088 [US5] Test post-password-change session invalidation: after password change, previous sessions are invalidated; user redirected to login
- [ ] T089 [US5] Test login with new password: after password change, user can log in with new password but NOT old password

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [ ] T090 [P] [US5] Verify password change endpoint contract per contracts/user-api.md: PUT /api/v1/users/password accepts {current_password, new_password}, returns 204 (200) or 400/401

### Implementation for User Story 5

- [ ] T091 Create password change service: `backend/src/services/auth_service.py` (extend)
  - Method `change_password(user_id: UUID, current_password: str, new_password: str) -> None`
  - Verify current_password against user's password_hash (bcrypt verify); raise ValidationError if mismatch
  - Validate new_password strength (≥8 chars, uppercase, lowercase, digit, special char) per FR-003
  - Hash new_password with bcrypt (12 rounds)
  - UPDATE users SET password_hash=hashed_new_password, updated_at=now WHERE id=?
  - Invalidate all existing sessions for user: UPDATE sessions SET is_active=FALSE WHERE user_id=?
  - Per FR-018, FR-015, data-model.md (session invalidation on password change)
- [ ] T092 Create password change endpoint: `backend/src/api/v1/user_routes.py` (extend)
  - `PUT /api/v1/users/password` → { current_password, new_password } → 204 No Content (or 400/401)
  - Requires authentication via get_current_user
  - Includes CSRF token requirement per FR-014
  - Sets Set-Cookie to clear current session (user must re-login with new password)
  - Per FR-018, FR-014
- [ ] T093 Create account settings page: `frontend/src/app/account/page.tsx`
  - Protected route: Requires authentication
  - Display profile info: email, created_at (from GET /api/v1/users/profile)
  - Display password change form
- [ ] T094 Create password change form component: `frontend/src/components/password-change-form.tsx`
  - Inputs: current_password, new_password, confirm_new_password
  - Client-side validation: new_password strength, passwords match
  - Submit: PUT /api/v1/users/password with CSRF token
  - On success: Redirect to /auth/login with message "Password changed, please log in again"
  - Per FR-018
- [ ] T095 [P] Extend API client: `frontend/src/lib/api-client.ts`
  - Function `getProfile()` calls GET /api/v1/users/profile
  - Function `changePassword(current, new)` calls PUT /api/v1/users/password with CSRF token
- [ ] T096 Add logging for password change: `backend/src/services/auth_service.py`
  - Log password change attempts (success/failure) with user_id (not passwords), timestamp
  - Log session invalidation events

**Checkpoint**: User Story 5 complete - users can view profile, change password, all sessions invalidated on password change

---

## Phase 8: Session Expiration & Rate Limiting Edge Cases (Concurrency & Timing Tests)

**Goal**: Verify session expiration logic (30-day rolling inactivity, cookie refresh, no absolute cap), rate limiting behavior, concurrency safety

### Tests for Session Expiration (Correction #3: Rolling Inactivity Only, No Absolute Cap with Cookie Refresh)

- [ ] T097 [P] Test 30-day inactivity expiration: session created with last_activity=T0 → advance time to T0+31 days with no intervening activity → GET /auth/me returns 401 (session expired by inactivity)
- [ ] T098 [P] Test inactivity counter reset: session created with last_activity=T0 → advance to T0+20 days, make activity request (GET /auth/me) which updates last_activity=T0+20 → inactivity timeout now at T0+20+30=T0+50 days → advance to T0+45 days and verify session still valid (no expiration)
- [ ] T099 [P] Test indefinite session validity with continuous activity: session created → user makes request every 25 days → verify session remains valid after 100+ days (no absolute expiration cap, only inactivity-based)
  - Verify last_activity is updated on each request
  - Verify expiration only checks NOW() - last_activity > 30 days (rolling window, no absolute cap)
- [ ] T099A [P] Test cookie refresh on authenticated request: log in at time T0 with session cookie Max-Age=2592000 → advance clock to T0+10 days → make authenticated GET request → verify response includes Set-Cookie with refreshed Max-Age=2592000 (30 days from T0+10, expiring at T0+40) → advance to T0+35 days and verify session still valid (both server last_activity and client cookie lifetime continuously extended) → proves active user remains authenticated beyond 30 calendar days

### Tests for Rate Limiting Edge Cases

- [ ] T100 [P] Test rate limit window: 5 failed attempts in window [0, 15 min) allowed; 6th at any point in [0, 15 min) blocked with 429; at T=15 min, counter resets, next 5 allowed
- [ ] T101 [P] Test rate limit per IP: requests from IP A and IP B tracked separately; IP A rate limited does not affect IP B

### Tests for Concurrency (Correction #3 & Data Model)

- [ ] T102 Test concurrent login race condition prevention: two simultaneous login requests for same user; database FOR UPDATE prevents both from succeeding; exactly one session created as active
- [ ] T103 Test concurrent password change: user logs in from two devices → change password on device A → verify device B session invalidated; device B cannot use old session

**Implementation Tasks (no code, only test verification)**

- [ ] T104 Verify session expiration tests pass with mocked time (pytest-freezegun or similar to mock time)
- [ ] T105 Verify rate limiting tests pass with isolated IP addresses and time
- [ ] T106 Verify concurrency tests pass; database locks prevent race conditions

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories, validation, documentation

- [ ] T107 [P] Add comprehensive error handling across all endpoints
  - Catch all exceptions, return generic error responses (no stack traces)
  - Per FR-015 (no internal details exposed)
- [ ] T108 [P] Add structured logging throughout: `backend/src/core/logging.py`
  - JSON logs with timestamp, level, message, context (user_id, session_id, etc.)
  - Log all authentication/authorization events for audit trail
- [ ] T109 [P] Create comprehensive README: `backend/README.md`, `frontend/README.md`
  - Setup instructions, environment variables, running the app
  - Developer instructions for tests, linting, formatting
- [ ] T110 Configure environment variables: `.env.example` file
  - DATABASE_URL, EMAIL_PROVIDER (mock/prod), REDIS_URL (optional), LOG_LEVEL, etc.
  - Document which are required vs. optional
- [ ] T111 [P] Add CORS configuration: `backend/src/main.py` (extend, Correction #4)
  - Allow frontend origin (http://localhost:3000 for dev, deployed domain for prod)
  - Allow credentials (for cookies): credentials=True, allow_origins=[frontend_origin], allow_methods=["GET", "POST", "PUT"], allow_headers=["*"]
  - Per Correction #4 (Next.js/FastAPI architecture with secure cookies)
- [ ] T112 [P] Add health check endpoints: `backend/src/api/health_routes.py`
  - GET /health → { status: "ok" } (always returns 200)
  - GET /readiness → { status: "ready" } (checks database connectivity)
- [ ] T113 Run quickstart.md validation scenarios
  - Scenario 1: Register → Login → Logout (happy path)
  - Scenario 2: Cross-user access denied (403)
  - Scenario 3: Weak password rejected (400)
  - Scenario 4: Rate limiting (429 after 5 failures)
  - Scenario 5: Session timeout (401 after 30 days inactivity)
  - Scenario 6: Password change invalidates sessions
  - Verify all scenarios pass with curl commands from quickstart.md
- [ ] T114 Frontend accessibility review
  - Semantic HTML on all forms
  - ARIA labels on inputs
  - Keyboard navigation (Tab through form fields)
  - Color contrast (WCAG 2.2 AA minimum)
- [ ] T115 [P] Commit strategy
  - Commit after each major component (e.g., after T026, T064, T092, etc.)
  - Commit message: Clear intent + user story reference (e.g., "feat(US1): implement user registration with validation and tests")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phases 3-7)**: All depend on Foundational completion
  - User Stories 1-4 are P1 (must complete before P2)
  - User Story 5 is P2 (lower priority)
  - Stories can proceed in parallel once Foundational is done
- **Concurrency/Expiration Tests (Phase 8)**: Depends on US2, US3, US5 foundations (sessions, logout, password change)
- **Polish (Phase 9)**: Depends on desired user stories being complete

### Within Foundational Phase (Phase 2)

All tasks marked [P] can run in parallel:
- Models (T011, T012, T013) can be created simultaneously
- Email providers (T016, T017) can be created simultaneously
- Security modules (T018, T019, T020) can be created simultaneously
- Repositories (T025, T026, T027) can be created simultaneously

### User Story Dependencies

- **User Story 1 (Registration, P1)**: Depends on Foundational; no dependencies on other stories (independent)
- **User Story 2 (Login, P1)**: Depends on Foundational and US1 (registrations must exist to log in)
- **User Story 3 (Logout, P1)**: Depends on Foundational and US2 (must be logged in to log out)
- **User Story 4 (Authorization, P1)**: Depends on Foundational and US2 (must verify authenticated user for authorization)
- **User Story 5 (Account, P2)**: Depends on Foundational and US4 (must have authenticated user to view/edit profile)

### Parallel Opportunities

**Phase 2 (Foundational)**: Models, email providers, security modules, repositories can all run in parallel (different developers)

**User Stories**: Each story has independent tests → backend service → endpoint/frontend tasks; all [P] tasks within story can run in parallel

**Full Team Strategy** (after Foundational):
- Developer A: US1 (Registration)
- Developer B: US2 (Login)
- Developer C: US3 (Logout)
- Developer D: US4 (Authorization)
- Developer E: US5 (Account)

All stories proceed in parallel post-Foundational completion.

---

## Implementation Strategy

### MVP First (User Stories 1-4 + Tests)

**Recommended for interview**: Complete core authentication loop with comprehensive test coverage

1. **Phase 1**: Setup (1-2 hours)
2. **Phase 2**: Foundational (4-6 hours) — database, models, repositories, security, API infrastructure
3. **Phase 3**: US1 Registration + tests (2-3 hours)
4. **Phase 4**: US2 Login + tests + concurrency tests (2-3 hours)
5. **Phase 5**: US3 Logout + tests (1-2 hours)
6. **Phase 6**: US4 Authorization + tests (1-2 hours)
7. **Stop here and validate** — test all scenarios from quickstart.md
8. **Deploy/demo MVP** — working authentication system with comprehensive test coverage

**Total MVP time**: 12-19 hours with tests

### Incremental Delivery

After MVP, add remaining features:

9. **Phase 7**: US5 Account + tests (1-2 hours)
10. **Phase 8**: Session expiration & rate limiting edge case tests (1-2 hours)
11. **Phase 9**: Polish (1-2 hours) — error handling, logging, validation
12. **Final validation**: All 6 scenarios from quickstart.md pass

**Total with P2 + tests**: 15-25 hours

### Test-First Development (TDD)

**For each user story**:
1. Write all tests (unit, integration, contract) for the story
2. Verify all tests FAIL (red phase)
3. Implement the feature
4. Verify all tests PASS (green phase)
5. Refactor if needed (optional)
6. Commit

This ensures **100% test coverage for implementation**, not optional validation.

---

## Format Validation

✓ All tasks use markdown checklist format (`- [ ]`)
✓ All tasks have Task IDs (T001+) in execution order
✓ Parallelizable tasks marked with [P]
✓ User story tasks marked with [Story] labels (US1-US5)
✓ All tasks include exact file paths
✓ **Tests are mandatory**, not optional (per Constitution Principle IV)
✓ Tests written before implementation (TDD)
✓ Session expiration logic explicitly defined (Correction #3)
✓ Email service abstracted, not required for v1 core (Correction #2)
✓ Frontend/backend cookie architecture explicit for Next.js + FastAPI (Correction #4)
✓ Concurrency safety (FOR UPDATE, transactions) explicit in tasks

---

## Notes

- [P] tasks have different files, no blocking dependencies → run in parallel
- [Story] label (US1-US5) maps task to specific user story for traceability
- **Tests are REQUIRED** (Constitution Principle IV): Unit, integration, negative, authorization, session-expiration, rate-limit, password-change, concurrency tests
- Database transaction safety ensured via SELECT ... FOR UPDATE on user row during login (READ COMMITTED isolation level, per data-model.md)
- Single-session enforcement: Concurrent logins prevented by row-level database locking
- Session expiration (Correction #3): Rolling inactivity only (NOW() - last_activity > 30 days); NO absolute expiration cap; any activity updates last_activity, extending timeout to last_activity + 30 days indefinitely
- **Cookie refresh mechanism**: On every authenticated request, session validation updates last_activity AND response middleware refreshes session cookie Max-Age=2592000 (30 days). This ensures both server-side (last_activity) and client-side (cookie lifetime) rolling windows are synchronized. Active users remain authenticated indefinitely because both expirations are continuously reset.
- Email service (Correction #2): Abstracted provider, mock for tests, stub for prod; not required for v1 core
- Frontend/Backend (Correction #4): Next.js sends session cookie automatically (same-origin, credentials: include); FastAPI validates via get_current_user dependency and refreshes cookie on authenticated response
- Commit after each major task or logical group (e.g., after T026, T064, T092)
- Stop at any checkpoint to validate story independently before proceeding
- Account deletion: Out of scope for v1; document in future backlog
- Session analytics/metrics: Out of scope for v1 MVP; Phase 9 observability task (T108) covers basic logging; detailed metrics deferred

