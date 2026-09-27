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
- **Migrations**: `backend/migrations/versions/`
- **Tests**: `backend/tests/{unit,integration,contract}` and colocated frontend tests under `frontend/src/`

**Status baseline**: Checkboxes below were reconciled against the implementation and tests on `origin/main` at `8d84fc35a6aae3e6b396fd3375ccccf8a2cadd76`. A checked task means its described implementation or test artifact is present; external deployment checks and unimplemented tests remain unchecked.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency configuration

- [x] T001 Create the backend, frontend, migration, and test directory structure used by the repository (`backend/src/`, `backend/tests/`, `frontend/src/`, `backend/migrations/versions/`)
- [x] T002 Configure the Python project and backend dependencies in `backend/pyproject.toml`
- [x] T003 [P] Configure the Next.js/TypeScript frontend and test scripts in `frontend/package.json`
- [x] T004 [P] Configure Python linting and formatting in `backend/`
- [x] T005 [P] Configure frontend linting and formatting in `frontend/`
- [x] T006 Configure environment-driven database settings in `backend/src/core/config.py`
- [x] T007 Initialize Alembic configuration and the migration directory under `backend/migrations/`
- [x] T008 Create pytest database, client, user, and mock-provider fixtures in `backend/tests/conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure MUST complete before ANY user story implementation

**CRITICAL**: No user story work can begin until this phase completes

### Database & Models Setup

- [x] T009 Create the async SQLAlchemy database engine and session factory in `backend/src/database.py`
- [x] T010 Create the shared UUID/timestamp base model in `backend/src/models/base.py`
- [x] T011 [P] Create the SQLAlchemy User entity in `backend/src/models/user.py`
  - Fields per data-model.md: id (UUID PK), email (VARCHAR 255, UNIQUE, NOT NULL, CHECK email format), password_hash (VARCHAR 255, NOT NULL), created_at (TIMESTAMP NOT NULL DEFAULT NOW), updated_at (TIMESTAMP NOT NULL DEFAULT NOW)
- [x] T012 [P] Create the SQLAlchemy Session entity in `backend/src/models/session.py`
  - Implemented fields include id, user_id, created_at, last_activity, ip_address, user_agent, is_active, and the session-bound csrf_token; there is no expires_at column
  - **Session Timeout (Rolling Inactivity Only)**: Session expires only when NOW() - last_activity > 30 days. There is NO absolute expiration cap. On each authenticated request, last_activity is updated, extending the timeout to last_activity + 30 days. Sessions remain valid indefinitely while the user is active.
- [x] T013 [P] Create the LoginAttempt audit entity in `backend/src/models/login_attempt.py`
  - Fields per data-model.md: id (UUID PK), email (VARCHAR 255 NOT NULL), ip_address (INET NOT NULL), attempted_at (TIMESTAMP NOT NULL DEFAULT NOW), success (BOOLEAN NOT NULL), failure_reason (VARCHAR 100, CHECK constraint: success=TRUE ⟹ failure_reason IS NULL AND success=FALSE ⟹ failure_reason IS NOT NULL)
- [x] T014 Create the initial user/session/login-attempt migration in `backend/migrations/versions/001_create_users_sessions_tables.py`
  - Creates users, sessions, and login_attempts tables with their implemented constraints and indexes

### Email Service Foundation

- [x] T015 Create the optional email provider abstraction in `backend/src/core/email_provider.py`
  - Abstract base class `EmailProvider` with method `send_notification(recipient: str, subject: str, body: str) -> bool`
  - Returns bool (success/failure); raises no exceptions; logs failures internally
  - Rationale per spec clarification: Email delivery is best-effort, non-blocking; account creation succeeds regardless
  - Email is used ONLY for optional notifications (password reset, security alerts - future); NOT required for v1 core registration/login
- [x] T016 [P] Create the mock email provider in `backend/src/core/email_provider_mock.py`
  - Implements EmailProvider; stores emails in in-memory log for test verification
  - `get_sent_emails() -> list` for test assertions (verify email was/wasn't sent)
  - Default provider in tests; never calls external service
- [x] T017 [P] Create the production email provider stub in `backend/src/core/email_provider_prod.py`
  - Stub implementation: logs "would send email to {recipient}" but does not call any service
  - Ready for integration with SendGrid/AWS SES/etc. in future sprints
  - Email delivery is out of scope for v1; stub allows infrastructure readiness

### Security & Authentication Foundations

- [x] T018 Create password hashing and token utilities in `backend/src/core/security.py`
  - Function `hash_password(password: str) -> str` using bcrypt with 12 salt rounds
  - Function `verify_password(plain: str, hashed: str) -> bool` for password verification
  - Function `generate_session_id() -> str` for cryptographically random UUID session tokens
- [x] T019 Implement CSRF token generation and constant-time comparison in `backend/src/core/security.py`, and session-bound token validation in `backend/src/api/v1/deps.py`
- [x] T019A Test CSRF behavior in `backend/tests/integration/test_auth_endpoints.py`
  - Test missing, invalid, cross-session, revoked-session, and expired-session tokens/credentials against password change and logout
  - Per FR-014 (CSRF protection required) and SC-010 (CSRF tokens prevent forgery attacks)
- [x] T020 Implement session validation and rolling inactivity in `backend/src/core/session_validator.py`
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

- [x] T021 Configure the FastAPI application, CORS, middleware, and exception handlers in `backend/src/main.py`
  - FastAPI instance, middleware setup (CORS, logging), exception handlers (return generic errors, no stack traces)
  - CORS configuration per Correction #4 (NextJS/FastAPI architecture): Allow frontend origin with credentials=True
- [x] T022 Define application exceptions and the generic error envelope in `backend/src/core/exceptions.py` and `backend/src/main.py`
  - Custom exception classes: ValidationError, AuthenticationError, AuthorizationError, RateLimitError
  - Error response envelope: {detail, status_code, error_code}
- [x] T023 Implement database, authenticated-user, and CSRF dependencies in `backend/src/api/v1/deps.py`
  - `get_db()` dependency for database session
  - `get_current_user()` dependency for authenticated user extraction from session cookie
    - Calls `validate_session()` to check inactivity and get user_id
    - If valid and refresh_cookie=True: Injects a response header or context to signal caller to refresh session cookie with Set-Cookie Max-Age=2592000
    - Extracts the session_id from the secure HttpOnly cookie; same-origin BFF cookie forwarding is covered by T056/T067
  - Per Correction #4: Cookie refresh happens at middleware/response layer (after successful request completion)
- [x] T024 Implement per-IP login rate limiting in `backend/src/core/rate_limiter.py` using Redis when available and process-local fallback otherwise

### Data Access Layer (Repositories)

- [x] T025 Implement parameterized User data access in `backend/src/repositories/user_repository.py`
  - Methods: `create_user(email: str, password_hash: str) -> User`, `get_user_by_email(email: str) -> User`, `get_user_by_id(id: UUID) -> User`, `user_exists(email: str) -> bool`
  - All using parameterized queries (SQLAlchemy ORM)
- [x] T026 Implement session creation, activity updates, invalidation, and active-session lookup in `backend/src/repositories/session_repository.py`
  - Methods: `create_session(user_id: UUID, ...) -> Session`, `get_session(session_id: str) -> Session`, `update_session_activity(session_id: str)`, `invalidate_session(session_id: str)`, `invalidate_user_sessions(user_id: UUID)`, `get_active_session(user_id: UUID) -> Session`
- [x] T027 Implement login-attempt persistence and failed-attempt queries in `backend/src/repositories/login_attempt_repository.py`
  - Methods: `log_attempt(email: str, ip: str, success: bool, reason: str)`, `count_failed_attempts(ip: str, minutes: int) -> int`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - New User Registration (Priority: P1) 🎯 MVP

**Goal**: Allow new users to create accounts with email/password, validate inputs, hash passwords securely, prevent duplicates

**Independent Test**: Navigate to registration form → enter valid email + strong password → submit → verify account exists in database and user can log in with those credentials

### Tests for User Story 1 (TDD - write FIRST, verify FAIL before implementation)

**Unit Tests: `backend/tests/unit/test_auth_service.py`**

- [x] T028 [P] [US1] Test registration validation: email format validation per RFC 5322, reject invalid formats
- [x] T029 [P] [US1] Test password strength enforcement: minimum 8 characters, require uppercase, lowercase, digit, special character; reject weak passwords
- [x] T030 [P] [US1] Test duplicate email prevention: second registration with same email returns ConflictError (409)
- [x] T031 [P] [US1] Test password hashing: registered password is hashed with bcrypt, never stored plaintext; `verify_password()` returns True for correct password, False for incorrect

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py`**

- [x] T032 [P] [US1] Test registration endpoint: POST /api/v1/auth/register with valid email/password returns 201 with user_id, email, created_at, and a persisted User record
- [x] T033 [P] [US1] Test registration error cases: invalid email returns 400, weak password returns 400, duplicate email returns 409, validation errors include error_code field
- [x] T034 [P] [US1] Test immediate login after registration: registered user can log in with provided credentials and receive session

**Contract Tests: `backend/tests/contract/test_auth_api.py`**

- [x] T035 [P] [US1] Verify registration endpoint contract per contracts/auth-api.md: POST /api/v1/auth/register accepts {email, password}, returns {user_id, email, created_at} or error envelope

### Implementation for User Story 1

- [x] T036 Create User registration service: `backend/src/services/auth_service.py`
  - Method `register_user(email: str, password: str) -> dict`
  - Validates email format (RFC 5322 compliant), password strength (≥8 chars, uppercase, lowercase, digit, special char)
  - Checks for duplicate email (email uniqueness)
  - Hash password with bcrypt (12 rounds), create User record
  - Returns user_id, email, created_at
  - Raises ValidationError (400), ConflictError (409)
  - Per FR-001, FR-002, FR-003, FR-004
- [x] T037 Create registration endpoint: `backend/src/api/v1/auth_routes.py`
  - `POST /api/v1/auth/register` → { email, password } → { user_id, email, created_at } (201) or error (400/409)
  - Input validation via Pydantic models
  - HTTPS required (enforced at deployment)
  - Per FR-001, FR-002, FR-003, FR-004
- [x] T038 [P] Create registration form component: `frontend/src/components/registration-form.tsx`
  - Email input (with validation display)
  - Password input (with strength indicator per FR-003: ≥8 chars, uppercase, lowercase, digit, special char)
  - Submit button, error/success messages
  - Client-side validation matches backend (email format, password strength)
- [x] T039 [P] Create registration page: `frontend/src/app/auth/register/page.tsx`
  - Route: /auth/register (public, no auth required)
  - Renders RegistrationForm component
  - On success: Navigate to /auth/login with message "Account created successfully"
- [x] T040 [P] Create API client for registration: `frontend/src/lib/api-client.ts`
  - Function `register(email: string, password: string)` calls POST /api/v1/auth/register
  - Handles errors, returns response or throws
  - Per Correction #4: Use credentials: 'include' for cross-site cookie handling
- [x] T041 Add logging for registration: `backend/src/services/auth_service.py`
  - Log registration attempts (success/failure) with email (not password), timestamp
  - Log validation errors (weak password, invalid email, duplicate email)

**Checkpoint**: User Story 1 complete - new users can register with validated email/password

---

## Phase 4: User Story 2 - Existing User Login (Priority: P1)

**Goal**: Allow registered users to log in, establish secure server-side sessions, set httpOnly cookies, enforce single-session per user with database locking, handle rate limiting

**Independent Test**: Log in with correct email + password → verify session cookie set → verify GET /auth/me returns user → verify access to protected pages works → log in from another device to verify single-session enforcement (previous session invalidated)

### Tests for User Story 2 (TDD - write FIRST, verify FAIL before implementation)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [x] T042 [P] [US2] Test login validation: correct password succeeds; incorrect password and unknown email fail with the same generic error
- [x] T043 [P] [US2] Test sequential single-session enforcement: a later login invalidates the prior session and leaves only one active session
- [x] T044 [P] [US2] Test per-IP rate limiting and expiration of the 15-minute failed-attempt window

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [x] T045 [P] [US2] Test successful login response and session cookie attributes (HttpOnly, Secure, SameSite=Strict, Max-Age=2592000) in `backend/tests/contract/test_auth_api.py`; missing-attribute negative cases are not covered
- [x] T046 [P] [US2] Test generic 401 errors for invalid credentials and 429 for a rate-limited login
- [x] T047 [P] [US2] Verify login omits session_id from the response body and sets the session cookie; cookie opacity is not directly asserted
- [x] T048 [US2] Test simultaneous logins and assert exactly one active session remains; both requests may succeed
- [x] T049 [US2] Verify session persistence by transferring the secure Max-Age cookie to a fresh client context, authenticating `/auth/me`, rejecting an invalid session, and restoring authenticated navigation after current-user validation
- [x] T050 [US2] Test six failed attempts, rate-limit response, and reset behavior using the configured limiter
- [x] T050A [US2] Verify authenticated requests refresh the cookie and rolling inactivity tests keep active sessions valid beyond 30 days; the exact day-10/day-35 scenario is covered across separate tests, not one combined case

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [x] T051 [P] [US2] Verify login success, error envelope, and cookie contract in `backend/tests/contract/test_auth_api.py`

### Implementation for User Story 2

- [x] T052 Implement login service with rate limiting, row locking, prior-session invalidation, session creation, and attempt audit persistence in `backend/src/services/auth_service.py`
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
- [x] T053 Implement the login endpoint and secure session-cookie attributes in `backend/src/api/v1/auth_routes.py`
  - `POST /api/v1/auth/login` → { email, password } → { user_id, email } (200) + Set-Cookie header (401/429 on error)
  - Extracts client IP (from X-Forwarded-For or REMOTE_ADDR)
  - Sets session cookie: httpOnly, Secure, SameSite=Strict, Max-Age=2592000 (30 days), Path=/
  - Per FR-019 (rate limiting), FR-020 (secure cookie flags), data-model.md (concurrency)
- [x] T053A Implement authenticated response cookie refresh in `backend/src/middleware/session_refresh.py`
  - Middleware/decorator that runs after successful authenticated request
  - If `get_current_user()` returned refresh_cookie=True: respond with Set-Cookie header refreshing session cookie Max-Age=2592000
  - Ensures cookie lifetime is continuously refreshed on every authenticated request, maintaining rolling inactivity window
  - Per FR-020 (refresh cookie on activity) and SC-012 (rolling inactivity with cookie refresh)
- [x] T054 [P] Implement the login form in `frontend/src/components/login-form.tsx`
  - Email and password inputs
  - Submit button, error display (generic "invalid credentials" per FR-013 acceptance scenario)
  - Submission sends POST to /api/v1/auth/login
- [x] T055 [P] Implement the public login page in `frontend/src/app/auth/login/page.tsx`
  - Route: /auth/login (public, no auth required)
  - Renders LoginForm
  - On 401/429 error: Display error message (rate limiting message for 429)
  - On success: Redirect to authenticated home (e.g., /dashboard or /orders)
- [x] T056 [P] Implement same-origin Next.js auth BFF handlers under `frontend/src/app/api/auth/` for register, login, logout, current-user, CSRF, and password operations. Use server-only `API_INTERNAL_URL`; explicitly forward Cookie and CSRF headers and relay safe status/error bodies and upstream Set-Cookie attributes.
- [x] T057 Harden `frontend/middleware.ts`: validate through same-origin `/api/auth/me`, forward the incoming session Cookie, redirect only on 401, preserve refreshed cookies, and distinguish upstream/network failures from an invalid session.
- [x] T058 Persist login attempts and emit success/failure/rate-limit security audit events without logging passwords in `backend/src/services/auth_service.py`
  - Log all login attempts (success/failure) with email (not password), IP address, timestamp
  - Log rate limit triggers

**Checkpoint**: Backend login/session behavior, same-origin BFF handlers (T056), middleware session validation (T057), browser API-client migration (T095), and protected-page coverage (T062) are implemented.

---

## Phase 5: User Story 3 - User Logout (Priority: P1)

**Goal**: Allow users to terminate their session, clear cookies, verify access denied after logout

**Independent Test**: Log in → log out → verify session terminated (GET /auth/me returns 401) → verify protected routes redirect to login

### Tests for User Story 3 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [x] T059 [P] [US3] Test logout invalidation: the session is marked inactive and subsequent authenticated lookup fails

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [x] T060 [US3] Test logout endpoint returns 204, clears the cookie, and invalidates the database session
- [x] T061 [US3] Test logout without a valid session returns 401 Unauthorized
- [x] T062 [US3] Verify an invalidated session redirects a protected page to login in `frontend/middleware.test.ts`; backend logout tests also verify `/auth/me` returns 401

### Implementation for User Story 3

- [x] T063 Implement logout session invalidation in `backend/src/services/auth_service.py`
  - Method `logout_user(session_id: str)`
  - UPDATE sessions SET is_active=FALSE WHERE id=?
  - Logs logout event (success only, not failures)
  - Per FR-008, FR-009
- [x] T064 Implement the CSRF-protected logout endpoint and session-cookie clearing in `backend/src/api/v1/auth_routes.py`
  - `POST /api/v1/auth/logout` → {} → 204 No Content (or 401 if session invalid)
  - Sets Set-Cookie header to clear session_id (Max-Age=0, Expires=1970-01-01)
  - Per FR-008, FR-009
- [x] T065 Implement the logout button in `frontend/src/components/logout-button.tsx`
  - Button triggers POST to /api/v1/auth/logout
  - On success: Redirect to /auth/login
- [x] T066 Show the logout button in authenticated navigation in `frontend/src/components/nav.tsx`
  - Visible only to authenticated users
  - Uses LogoutButton component
- [x] T067 Add integrated middleware, BFF, and API-client tests for cookie forwarding, logout-invalidated 401 redirects, non-401/upstream/network failures, route and CSRF forwarding, cookie relay/clearing, and same-origin auth callers
- [x] T068 Emit a secret-safe logout audit event from the route with user and client context in `backend/src/api/v1/auth_routes.py`; session IDs are intentionally not logged

**Checkpoint**: Backend logout and the client logout control are implemented. Middleware cookie forwarding and invalidated-session redirect behavior are covered by T057, T062, and T067.

---

## Phase 6: User Story 4 - Authenticated User Identity & Authorization Boundaries (Priority: P1)

**Goal**: Correctly identify authenticated users, enforce 403 Forbidden on cross-user access, maintain identity throughout session

**Independent Test**: Log in as User A → attempt to access User B's resource (e.g., /api/users/{user-b-id}) → verify 403 response; Log in as User A → verify /api/orders returns only User A's orders; Log out → verify 401 on subsequent requests

### Tests for User Story 4 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [x] T069 [P] [US4] Test the owner and non-owner policy in `backend/tests/unit/test_authorization.py`; route-level tests remain conditional on a concrete user-owned resource endpoint
- [ ] T070 [P] [US4] Add cross-user authorization tests when a concrete user-owned resource route is introduced; Feature 001 defines no target-user profile or commerce resource route

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [x] T071 [P] [US4] Assert the full `/api/v1/auth/me` response schema and 200/401 behavior in `TestCurrentUserEndpoint`
- [ ] T072 [P] [US4] Add a cross-user access integration test when a concrete user-owned resource route is in scope; no target-user profile route exists in Feature 001
- [ ] T073 [P] [US4] Verify owner and non-owner behavior on each concrete user-scoped route when those routes are added; specify each route's status contract then
- [x] T074 [US4] Test that logout invalidation makes a subsequent `/api/v1/auth/me` request return 401

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [x] T075 [P] [US4] Verify authenticated `/api/v1/users/profile` success and unauthenticated 401 responses in `TestUserProfileContract`

### Implementation for User Story 4

- [x] T076 Implement `GET /api/v1/auth/me` with authenticated user identity in `backend/src/api/v1/auth_routes.py`
  - `GET /api/v1/auth/me` → {} → { user_id, email, created_at } (200) or 401
  - Requires valid session (validated via get_current_user dependency)
  - Per FR-010, FR-017
- [x] T077 Use the `get_current_user()` dependency in `backend/src/api/v1/deps.py` to validate the session and provide the authenticated user ID; no separate `require_auth()` decorator is used
- [x] T078 Define `verify_user_owns_resource(user_id: UUID, resource_owner_id: UUID) -> bool` in `backend/src/core/authorization.py`; it returns True for the owner and raises a generic `AuthorizationError` (403) otherwise. Concrete routes must call it when they accept resource IDs.
- [x] T079 Implement the authenticated self-profile endpoint in `backend/src/api/v1/user_routes.py`
  - `GET /api/v1/users/profile` → {} → { user_id, email, created_at } (200) or 401
  - Requires authentication via get_current_user
  - Returns only the authenticated user's own profile (implicit ownership)
  - Per FR-010, FR-011, FR-017
- [ ] T080 Apply `verify_user_owns_resource` at each concrete user-scoped endpoint when those routes are introduced; `/api/v1/users/profile` has no caller-supplied target user ID
- [x] T081 [P] Keep navigation authentication state local to `frontend/src/components/nav.tsx`; `nav.test.tsx` covers signed-in, signed-out, loading, and no-probe states, so a separate global auth context is not required
- [x] T082 [P] Implement the authenticated dashboard page in `frontend/src/app/dashboard/page.tsx`; completing middleware cookie forwarding remains T057
  - Protected route: Requires authentication (checked by middleware)
  - Displays current user info via GET /auth/me
  - Per FR-010, FR-017
- [x] T083 Emit secret-safe authentication and authorization-denial audit events in `backend/src/core/observability.py` and `backend/src/main.py`; resource attribution remains inapplicable until resource routes are defined

**Checkpoint**: Authenticated identity, self-profile access, invalid-session rejection, and a reusable owner policy are implemented and tested. Concrete cross-user 403 route behavior remains pending until a user-owned resource endpoint is in scope.

---

## Phase 7: User Story 5 - Account Information Access (Priority: P2)

**Goal**: Allow users to view their profile (email, created_at), change password with current password verification, invalidate all sessions on password change

**Independent Test**: Log in → view profile (GET /api/v1/users/profile) → change password with correct current password → verify old password fails on re-login → verify new password works → verify all other sessions invalidated (forced logout on other devices)

### Tests for User Story 5 (TDD)

**Unit Tests: `backend/tests/unit/test_auth_service.py` (extend)**

- [x] T084 [P] [US5] Test incorrect current password, weak new password, and strong password hashing in `TestPasswordChange`
- [x] T085 [P] [US5] Test password change invalidates all active sessions in `TestPasswordChange`

**Integration Tests: `backend/tests/integration/test_auth_endpoints.py` (extend)**

- [x] T086 [P] [US5] Test password-change success and subsequent authentication with the new password in `TestPasswordChangeEndpoint`
- [x] T087 [P] [US5] Test wrong current password, weak new password, revoked/expired sessions, and missing/invalid CSRF in the password-change endpoint tests
- [x] T088 [US5] Test multi-session invalidation and the account UI's login redirect after password change in backend integration and `account-page.test.tsx`
- [x] T089 [US5] Verify old-password login fails and new-password login succeeds after a password change in `TestPasswordChangeEndpoint`

**Contract Tests: `backend/tests/contract/test_auth_api.py` (extend)**

- [x] T090 [P] [US5] Cover `PUT /api/v1/users/password` success, validation, authentication, and CSRF responses in `TestPasswordChangeContract`

### Implementation for User Story 5

- [x] T091 Implement password verification, new-password validation/hashing, and session invalidation in `backend/src/services/auth_service.py`
  - Method `change_password(user_id: UUID, current_password: str, new_password: str) -> None`
  - Verify current_password against user's password_hash (bcrypt verify); raise ValidationError if mismatch
  - Validate new_password strength (≥8 chars, uppercase, lowercase, digit, special char) per FR-003
  - Hash new_password with bcrypt (12 rounds)
  - UPDATE users SET password_hash=hashed_new_password, updated_at=now WHERE id=?
  - Invalidate all existing sessions for user: UPDATE sessions SET is_active=FALSE WHERE user_id=?
  - Per FR-018, FR-015, data-model.md (session invalidation on password change)
- [x] T092 Implement the authenticated, CSRF-protected password-change endpoint in `backend/src/api/v1/user_routes.py`; current session invalidation is server-side, while same-origin cookie clearing/relay belongs to the pending BFF work
  - `PUT /api/v1/users/password` → { current_password, new_password } → 204 No Content (or 400/401)
  - Requires authentication via get_current_user
  - Includes CSRF token requirement per FR-014
  - Sets Set-Cookie to clear current session (user must re-login with new password)
  - Per FR-018, FR-014
- [x] T093 Implement the account page with profile and password-change UI in `frontend/src/app/account/page.tsx`
  - Protected route: Requires authentication
  - Display profile info: email, created_at (from GET /api/v1/users/profile)
  - Display password change form
- [x] T094 Keep the password-change form inline in the account page; it collects current/new/confirmation values, performs basic client checks, submits CSRF, and navigates to login after success
- [x] T095 [P] Migrate `getProfile()`, `changePassword()`, and the login/logout/register calls in `frontend/src/lib/api-client.ts` from direct FastAPI URLs to the same-origin BFF handlers after T056
- [x] T096 Emit secret-safe password-change audit events without logging passwords; a separate session-invalidation audit event is not currently emitted

**Checkpoint**: User Story 5 complete - users can view profile, change password, all sessions invalidated on password change

---

## Phase 8: Session Expiration & Rate Limiting Edge Cases (Concurrency & Timing Tests)

**Goal**: Verify session expiration logic (30-day rolling inactivity, cookie refresh, no absolute cap), rate limiting behavior, concurrency safety

### Tests for Session Expiration (Correction #3: Rolling Inactivity Only, No Absolute Cap with Cookie Refresh)

- [x] T097 [P] Test the inactivity expiration boundary with mocked time: a request at the 30-day boundary succeeds and one just after it returns 401
- [x] T098 [P] Test that authenticated activity resets the inactivity window using mocked time
- [x] T099 [P] Test that repeated activity keeps a session valid beyond 100 days and that expiration is based only on inactivity
  - Verify last_activity is updated on each request
  - Verify expiration only checks NOW() - last_activity > 30 days (rolling window, no absolute cap)
- [x] T099A [P] Verify cookie refresh on authenticated requests and active-session validity beyond 30 days across T050A/T097-T099 tests; the originally described day-10/day-35 combined timeline is not a single test

### Tests for Rate Limiting Edge Cases

- [x] T100 [P] Test the five-failure threshold, 429 response, and reset after the 15-minute window
- [x] T101 [P] Prove rate-limit attempts are isolated by IP in `test_rate_limited_ip_does_not_affect_another_ip`

### Tests for Concurrency (Correction #3 & Data Model)

- [x] T102 Test simultaneous login requests and assert exactly one active session remains; both login requests are expected to succeed sequentially under the row lock
- [x] T103 Prove password change invalidates multiple previously active sessions in `TestPasswordChangeEndpoint`

**Implementation Tasks (no code, only test verification)**

- [x] T104 Verify the mocked-time session expiration and rolling-activity tests pass (`TestRollingSessionTimeout`)
- [x] T105 Verify IP-isolated and mocked-window rate-limit tests pass (`TestRateLimitingIntegration`, `test_rate_limiter.py`)
- [x] T106 Verify the simultaneous-login row-lock test passes against the configured PostgreSQL test database (`TestSingleSessionConcurrency`)

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories, validation, documentation

- [x] T107 [P] Return generic error envelopes from application and unexpected exception handlers without exposing stack traces in `backend/src/main.py`
  - Catch all exceptions, return generic error responses (no stack traces)
  - Per FR-015 (no internal details exposed)
- [x] T108 [P] Configure structured logging, request IDs, bounded in-process metrics, and security audit events in `backend/src/core/observability.py`; the implementation is not `core/logging.py`
- [x] T109 [P] Document backend/frontend setup, environment variables, same-origin auth BFF usage, tests, linting, and formatting in `backend/README.md` and `frontend/README.md`
  - Setup instructions, environment variables, running the app
  - Developer instructions for tests, linting, formatting
- [x] T110 Document backend and frontend environment settings in their `.env.example` files
  - DATABASE_URL, EMAIL_PROVIDER (mock/prod), REDIS_URL (optional), LOG_LEVEL, etc.
  - Document which are required vs. optional
- [x] T111 [P] Configure explicit environment-driven CORS origins and credential support in `backend/src/main.py`; deployed-origin behavior is not verified here
- [x] T112 [P] Implement `/health` and database-backed `/readiness` in `backend/src/main.py`; they are not separate `api/health_routes.py` routes
  - GET /health → { status: "ok" } (always returns 200)
  - GET /readiness → { status: "ready" } (checks database connectivity)
- [ ] T113 Complete the deployed HTTPS browser quickstart when its prerequisites exist; local Next.js-to-FastAPI BFF checks prove the available API flows over HTTP using disposable SQLite and manually supplied cookies, but do not prove Secure-cookie browser continuity, PostgreSQL behavior, or cross-user route behavior (see `CLOSURE_EVIDENCE.md`)
  - Scenario 1: Register → Login → Logout (happy path)
  - Scenario 2: Cross-user access denied (403)
  - Scenario 3: Weak password rejected (400)
  - Scenario 4: Rate limiting (429 after 5 failures)
  - Scenario 5: Session timeout (401 after 30 days inactivity)
  - Scenario 6: Password change invalidates sessions
  - Verify all scenarios pass with curl commands from quickstart.md
- [ ] T114 Finish the manual assistive-technology review; local browser review covered registration/login semantics, account-page keyboard order, and validation recovery, and fixed the account form disappearing on validation error, but no screen reader was available (see `CLOSURE_EVIDENCE.md`)
  - Semantic HTML on all forms
  - ARIA labels on inputs
  - Keyboard navigation (Tab through form fields)
  - Color contrast (WCAG 2.2 AA minimum)

## Pending BFF Integration Tasks

- [x] T116 Test the auth BFF route map, server-only backend URL usage, Cookie/CSRF forwarding, status/error handling, and Set-Cookie relay/clearing in `auth-routes.test.ts`
- [x] T117 Migrate auth UI callers/tests to same-origin BFF paths, including registration through `api-client.register()`, and retain no-probe/authenticated-navigation coverage

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

1. **Phase 1**: Setup
2. **Phase 2**: Foundational — database, models, repositories, security, API infrastructure
3. **Phase 3**: US1 Registration + tests
4. **Phase 4**: US2 Login + tests + concurrency tests
5. **Phase 5**: US3 Logout + tests
6. **Phase 6**: US4 Authorization + tests
7. **Stop here and validate** — test all scenarios from quickstart.md
8. **Deploy/demo MVP** — working authentication system with comprehensive test coverage

**MVP scope**: Phases 1-6, tests, and validation

### Incremental Delivery

After MVP, add remaining features:

9. **Phase 7**: US5 Account + tests
10. **Phase 8**: Session expiration & rate limiting edge case tests
11. **Phase 9**: Polish — error handling, logging, validation
12. **Final validation**: All 6 scenarios from quickstart.md pass

**Full implementation scope**: Phases 1-9, P2 features, tests, and validation

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

## Checklist Validation

- All tasks use Markdown checkboxes to distinguish evidenced completion from pending work.
- Task IDs are unique; T019A is retained as an additional CSRF test task and T116-T117 cover BFF validation.
- [P] and [Story] labels identify concurrency and user-story ownership where applicable.
- Tests remain required; a checked test task means the corresponding test artifact exists, while explicit verification tasks remain unchecked until run.
- Session-bound CSRF, rolling inactivity, and row-lock-based single-session behavior are described using the implemented design.
- Browser authentication uses the same-origin BFF; the direct FastAPI client is retained only for the product catalog and backend contract/quickstart checks.

---

## Notes

- [P] tasks have different files, no blocking dependencies → run in parallel
- [Story] label (US1-US5) maps task to specific user story for traceability
- **Tests are REQUIRED** (Constitution Principle IV): Unit, integration, negative, authorization, session-expiration, rate-limit, password-change, concurrency tests
- Database transaction safety uses a user-row SELECT ... FOR UPDATE during login; exact isolation-level guarantees should be confirmed against the configured database before being claimed
- Single-session enforcement: Concurrent logins prevented by row-level database locking
- Session expiration (Correction #3): Rolling inactivity only (NOW() - last_activity > 30 days); NO absolute expiration cap; any activity updates last_activity, extending timeout to last_activity + 30 days indefinitely
- **Cookie refresh mechanism**: On every authenticated request, session validation updates last_activity AND response middleware refreshes session cookie Max-Age=2592000 (30 days). This ensures both server-side (last_activity) and client-side (cookie lifetime) rolling windows are synchronized. Active users remain authenticated indefinitely because both expirations are continuously reset.
- Email service (Correction #2): Abstracted provider, mock for tests, stub for prod; not required for v1 core
- Frontend/backend boundary: auth calls use a same-origin BFF that forwards the session cookie and CSRF header and relays session-cookie updates
- Stop at any checkpoint to validate story independently before proceeding
- Account deletion: Out of scope for v1; document in future backlog
- Production HTTPS and deployed CORS behavior: not verified by this local implementation review; SC-011 remains open
- Session analytics/metrics: detailed metrics beyond current bounded in-process metrics and audit events remain out of scope for this feature

## Phase 10: Convergence

- [x] T118 Align the Session entity in `spec.md` with implemented `is_active`/`last_activity` expiry and no persisted `expires_at`
- [x] T119 Clarify in `spec.md` that v1 registration sends no email and has no email-delay UI or failure path
- [x] T120 Align the US5 independent test in `spec.md` with profile viewing and password change only
- [ ] T121 When an actual deployed HTTPS target is provided, verify trusted TLS delivery and required secure headers on sensitive API responses, and record evidence for SC-011; no deployment URL or local HTTPS listener was available during closure review (see `CLOSURE_EVIDENCE.md`)

