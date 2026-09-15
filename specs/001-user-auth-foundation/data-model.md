# Data Model: User Authentication

**Feature**: User Authentication and Account Foundation

**Created**: 2026-09-15

## Entity Definitions

### User

**Purpose**: Represents a registered user account in ShopSmart AI

**Primary Key**: `id` (UUID, auto-generated)

**Fields**:

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| id | UUID | NOT NULL, PRIMARY KEY | Unique user identifier |
| email | string (255) | NOT NULL, UNIQUE, CHECK (valid email format) | User login identifier; globally unique |
| password_hash | string (255) | NOT NULL | Bcrypt-hashed password (12 salt rounds) |
| created_at | timestamp | NOT NULL, DEFAULT NOW() | Account creation timestamp (UTC) |
| updated_at | timestamp | NOT NULL, DEFAULT NOW() | Last profile update timestamp (UTC) |

**Validation Rules**:
- email: RFC 5322 compliant; lowercase; must be unique across all users
- password_hash: Never stored or logged in plaintext; must be bcrypt with ≥12 salt rounds
- created_at, updated_at: Always UTC; immutable (created_at), auto-updated on writes (updated_at)

**Indexes**:
- PRIMARY KEY on id
- UNIQUE on email (fast email lookup)
- INDEX on created_at (for audit/reporting)

**State Transitions**: None (users are not soft-deleted in v1; deactivation is out of scope)

**Relationships**:
- One-to-Many with Session (one user can have multiple sessions over time, but only one active at a time per single-session policy)
- One-to-Many with LoginAttempt (audit trail)

---

### Session

**Purpose**: Represents an authenticated browser session

**Primary Key**: `id` (UUID, auto-generated)

**Fields**:

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| id | UUID | NOT NULL, PRIMARY KEY | Session token/identifier (cryptographically random) |
| user_id | UUID | NOT NULL, FOREIGN KEY (User.id) | Links session to user account |
| created_at | timestamp | NOT NULL, DEFAULT NOW() | Session creation time (UTC) |
| last_activity | timestamp | NOT NULL, DEFAULT NOW() | Last request timestamp; updated on each authenticated request |
| ip_address | string (45) | NOT NULL | Client IP address (supports IPv4 and IPv6) |
| user_agent | string (500) | NOT NULL | Browser user-agent string for audit |
| is_active | boolean | NOT NULL, DEFAULT TRUE | Logical soft-delete for logout |

**Validation Rules**:
- id: Cryptographically random, 256-bit entropy (sufficient for ~128-bit security margin)
- user_id: Must reference existing User; foreign key enforced
- last_activity: Updated on every authenticated request; inactivity expiration computed as NOW() - last_activity > 30 days
- ip_address: Stored for audit/security; not used for session validation (multi-device access allowed)
- is_active: Set to FALSE on logout; queries filter is_active = TRUE
- **Session Timeout Logic (Rolling Inactivity Only)**: Session expires when NOW() - last_activity > 30 days. There is no absolute expiration cap; sessions remain valid indefinitely while the user is active. On each authenticated request, last_activity is updated, extending the timeout to last_activity + 30 days.

**Indexes**:
- PRIMARY KEY on id (fast session lookup)
- FOREIGN KEY on user_id (enforce referential integrity)
- INDEX on (user_id, is_active) (find active session for a user)
- INDEX on last_activity (cleanup of inactive sessions)

**State Transitions**:

```
Active Session:
  1. Created: is_active = TRUE, last_activity = NOW()
  2. Active Use: last_activity updated on each request
  3. Inactivity: After 30 days no activity, session is expired (not deleted, but rejected on validation)
  4. Logout: is_active = FALSE (immediate termination)
  5. Cleanup: Expired sessions can be archived/deleted after retention period (e.g., 90 days)
```

**Relationships**:
- Many-to-One with User (many sessions belong to one user; single-session policy means at most one active session per user)
- One-to-Many with LoginAttempt (optional; for failed-login audit per session)

---

### LoginAttempt

**Purpose**: Audit trail for login attempts; used for rate limiting and security monitoring

**Primary Key**: `id` (UUID)

**Fields**:

| Field | Type | Constraints | Purpose |
|-------|------|-----------|---------|
| id | UUID | NOT NULL, PRIMARY KEY | Unique attempt identifier |
| email | string (255) | NOT NULL | Email address attempted (may not exist) |
| ip_address | string (45) | NOT NULL | Client IP address |
| attempted_at | timestamp | NOT NULL, DEFAULT NOW() | Attempt timestamp (UTC) |
| success | boolean | NOT NULL | TRUE if login succeeded, FALSE if failed |
| failure_reason | string (100) | NULL | "invalid_email", "invalid_password", "user_not_found", etc. (only if success = FALSE) |

**Validation Rules**:
- email: Not validated; stored as-is for audit (may be invalid or non-existent)
- ip_address: Required; used for rate limiting queries
- success: If FALSE, failure_reason must be set; if TRUE, failure_reason must be NULL
- attempted_at: Always UTC

**Indexes**:
- PRIMARY KEY on id
- COMPOSITE INDEX on (ip_address, attempted_at) — for rate-limit queries ("count failures in last 15 minutes from this IP")
- INDEX on attempted_at (for cleanup/archival)

**State Transitions**: None (audit log is immutable append-only)

**Relationships**: Optional Many-to-One with Session (if succeeded and session created, can link to Session.id)

---

## Data Integrity Constraints

### Foreign Key Constraints

- Session.user_id → User.id (RESTRICT on delete; users cannot be deleted while sessions exist, or use CASCADE with caution)

### Uniqueness Constraints

- User.email: UNIQUE (prevent duplicate registrations)
- Session.id: PRIMARY KEY (tokens are unique)

### Check Constraints

- User.email: Valid email format (basic regex or trigger)
- Session.expires_at > Session.created_at (integrity check)
- Session.last_activity <= NOW() (activity cannot be in future)

---

## Database Schema (SQL)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET NOT NULL,
    user_agent VARCHAR(500) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (last_activity <= CURRENT_TIMESTAMP)
);

CREATE INDEX idx_sessions_user_id_active ON sessions(user_id, is_active);
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity);

-- LoginAttempts table (audit log)
CREATE TABLE login_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    ip_address INET NOT NULL,
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    CHECK (
        (success = TRUE AND failure_reason IS NULL) OR
        (success = FALSE AND failure_reason IS NOT NULL)
    )
);

CREATE INDEX idx_login_attempts_ip_timestamp ON login_attempts(ip_address, attempted_at);
CREATE INDEX idx_login_attempts_timestamp ON login_attempts(attempted_at);
```

---

## Validation & Business Rules

### Registration (User Creation)

1. Email must be valid RFC 5322 format → ERROR 400 if invalid
2. Email must not already exist → ERROR 409 if duplicate
3. Password must be ≥8 characters, include uppercase, lowercase, digit, special char → ERROR 400 if weak
4. Hash password using bcrypt (12 rounds) before storing
5. Create User record with email and password_hash
6. Log LoginAttempt with success = TRUE

### Login (Session Creation with Single-Session Enforcement)

**Transaction: Single-session-per-user with concurrency-safe locking**

Isolation Level: READ COMMITTED (PostgreSQL default)

```
BEGIN TRANSACTION (READ COMMITTED)
  1. Email must exist in User table → log attempt with success = FALSE if not found
  2. Password must match user's password_hash (bcrypt verify) → log attempt with success = FALSE if mismatch
  3. Check rate limiting: If >5 failed attempts from IP in last 15 minutes → ERROR 429
  4. SELECT user FROM users WHERE id = ? FOR UPDATE (row-level lock, prevents concurrent modifications)
  5. IF existing active session exists (SELECT * FROM sessions WHERE user_id = ? AND is_active = TRUE)
       THEN UPDATE sessions SET is_active = FALSE WHERE user_id = ? AND is_active = TRUE
  6. DELETE FROM sessions WHERE user_id = ? AND is_active = FALSE (cleanup old logged-out sessions, optional)
  7. CREATE Session record with:
       - id: cryptographically random UUID
       - user_id: from authenticated user
       - is_active: TRUE
       - created_at: NOW()
       - last_activity: NOW()
       - ip_address: client IP
       - user_agent: client user-agent
  8. COMMIT TRANSACTION
```

**Why READ COMMITTED + FOR UPDATE is sufficient**:

READ COMMITTED is PostgreSQL's default isolation level. Combined with `SELECT ... FOR UPDATE` on the user row:
- FOR UPDATE acquires an exclusive lock on the user row for the duration of the transaction
- While one login transaction holds the lock, other concurrent login transactions for the same user must wait
- When the first transaction commits (new session inserted), the lock is released
- The waiting transaction acquires the lock, checks for active sessions (now finds the one just created), invalidates it, and inserts its own
- Result: Only one active session per user, guaranteed by database-level locking, not isolation level

This is simpler and more performant than SERIALIZABLE isolation (which adds overhead for all rows accessed in the transaction) and more correct than optimistic locking patterns (which require retry logic).

**After successful transaction**:
1. Set session cookie with httpOnly, Secure, SameSite=Strict flags
2. Log LoginAttempt with success = TRUE

### Session Validation (on every request)

1. Extract session ID from cookie
2. Look up Session by id
3. Check is_active = TRUE → REJECT 401 if not
4. Check NOW() - last_activity > 30 days → REJECT 401 if inactivity timeout exceeded
5. If valid, update last_activity = NOW() (extend timeout to NOW() + 30 days)
6. Extract user_id and verify user still exists → REJECT 401 if user deleted
7. **No absolute expiration cap**: Session remains valid indefinitely while actively used (last_activity kept current)

### Logout (Session Termination)

1. Extract session ID from cookie
2. Set Session.is_active = FALSE
3. Clear session cookie from response
4. Return 204 No Content

### Authorization (accessing user-scoped resources)

1. Validate session (see above)
2. Extract user_id from session
3. For request accessing user resource (e.g., GET /api/users/{target_user_id}):
   - If target_user_id == session.user_id → ALLOW
   - Else → REJECT 403 Forbidden
4. Log all authorization failures for monitoring

### Password Change

1. Validate session (user must be authenticated)
2. Verify current_password matches user's password_hash
3. Hash new_password with bcrypt (12 rounds)
4. Update User.password_hash
5. Update User.updated_at = now()
6. Invalidate all existing sessions for user (set is_active = FALSE) to force re-login on all devices
7. Create new session for current device (re-authenticate after password change)
8. Return 204 No Content

---

## Migration Strategy

### Initial Schema Creation (Alembic migration)

File: `migrations/versions/001_create_user_auth_tables.py`

Operations:
1. Create users table with indexes
2. Create sessions table with foreign key and indexes
3. Create login_attempts table with indexes
4. Verify constraints are enforceable

### Future Migrations (post-v1)

- Add password_reset_token field if password reset is added
- Add two_factor_auth fields if MFA is added
- Archive old sessions/login_attempts after retention period
- Normalize ip_address storage if needed

---

## Performance Considerations

### Query Patterns & Optimization

**Session Lookup** (on every request): `SELECT * FROM sessions WHERE id = $1 AND is_active = TRUE`
- Index: PRIMARY KEY on id (automatically fast)
- Estimated: <1ms (hash lookup)

**Find User's Active Session**: `SELECT * FROM sessions WHERE user_id = $1 AND is_active = TRUE LIMIT 1`
- Index: COMPOSITE on (user_id, is_active) (essential for single-session enforcement)
- Estimated: <1ms

**Rate Limit Check**: `SELECT COUNT(*) FROM login_attempts WHERE ip_address = $1 AND attempted_at > NOW() - INTERVAL '15 minutes' AND success = FALSE`
- Index: COMPOSITE on (ip_address, attempted_at) (essential for frequent checks)
- Estimated: <10ms (even for busy IPs with thousands of attempts)

**Cleanup Expired Sessions**: `DELETE FROM sessions WHERE expires_at < NOW() AND is_active = FALSE`
- Index: on expires_at (supports efficient cleanup)
- Estimated: Batch job, non-blocking

### Caching Strategy (Optional Redis)

- Session cache key: `session:{session_id}` → {user_id, expires_at} (TTL = 30 days or session expiry)
  - Reduces database load for session lookups
  - On logout, invalidate cache immediately
  - Redis miss falls back to database lookup
- Rate-limit counter: `rate_limit:{ip_address}:{window}` → count (TTL = 15 minutes)
  - Atomic increment on each login attempt
  - Fast threshold checks
- User object cache: `user:{user_id}` → {id, email, created_at} (TTL = 24 hours)
  - Reduces profile lookups
  - Invalidate on password change

---

## Testing Data & Fixtures

### Test User Accounts

- **Valid User**: email="user@example.com", password="Secure123!" (hashed)
- **Weak Password Test**: password="123" (should fail validation)
- **Duplicate Email Test**: Create two accounts with same email (second should fail)

### Test Sessions

- **Active Session**: created_at = now, expires_at = now + 30 days, is_active = TRUE
- **Expired Session**: created_at = 31 days ago, expires_at = 1 day ago, is_active = TRUE (should be rejected)
- **Logged-out Session**: is_active = FALSE (should be rejected)

### Rate Limit Test Data

- **5 Failed Attempts**: Create 5 LoginAttempt records from same IP with success = FALSE (6th should be rate-limited)
- **Successful Login**: LoginAttempt with success = TRUE (should reset rate limit)

---

## Security & Audit

### Sensitive Data Handling

- password_hash: Never logged, never sent to frontend, never displayed
- Session tokens: Sent only via httpOnly cookies (never in JavaScript)
- IP address: Logged for audit; used for rate limiting and fraud detection

### Audit Trail

- All login attempts (success/failure) logged to login_attempts table
- All logouts recorded (Session.is_active = FALSE with timestamp)
- Password changes audit (User.updated_at changes)
- Suspicious patterns (>5 failures from IP) monitored for alerting

### Encryption at Rest

- Passwords: Bcrypt hashing (salt embedded in hash)
- Session tokens: Random UUIDs (no encryption needed; entropy sufficient)
- IP addresses: Stored plaintext (consider encryption if GDPR/privacy concern)

---

## Retention & Cleanup

### Data Retention Policies

- Users: Permanent (no deletion in v1)
- Active Sessions: Until logout or expiry (30 days inactivity)
- Expired/Logged-out Sessions: Keep for 90 days (audit), then delete
- LoginAttempts: Keep for 30 days (rate-limit and fraud detection), then archive

### Cleanup Jobs (recommended)

- Nightly: Delete expired sessions older than 90 days
- Weekly: Archive and compress old login_attempts (older than 30 days)

