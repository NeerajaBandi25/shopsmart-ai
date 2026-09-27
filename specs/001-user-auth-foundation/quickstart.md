# Quickstart Validation Guide

**Feature**: User Authentication and Account Foundation

**Version**: 1.0

**Date**: 2026-09-15

## Overview

This guide provides runnable validation scenarios to prove the authentication feature works end-to-end. Each scenario is independent and can be tested in isolation.

Browser authentication uses the same-origin Next.js `/api/auth/*` BFF, which forwards to FastAPI. The curl examples below call FastAPI directly to validate its API contract; they do not replace browser/BFF testing. Because session cookies are `Secure`, every cookie-based curl or browser scenario requires an HTTPS origin (for example, a local HTTPS reverse proxy); plain HTTP can exercise public registration/login responses but cannot validate authenticated cookie continuity.

---

## Prerequisites

### Environment Setup

1. **Database**: PostgreSQL running (local or containerized)
  - Connection string: `postgresql+asyncpg://user:password@localhost:5432/shopsmart_auth_test`
   - Tables created (users, sessions, login_attempts)
   - See [data-model.md](../data-model.md) for schema

2. **Backend Server**: FastAPI running
   - URL: `http://localhost:8000` (development) or `https://api.shopsmart.local` (staging)
   - Environment variables configured:
     - `DATABASE_URL=postgresql://...`
    - `SECRET_KEY=<unique-random-secret>`
     - `REDIS_URL=redis://localhost:6379` (optional, for rate limiting)

3. **Frontend Application**: Next.js running
   - URL: `http://localhost:3000` (development)
  - `API_INTERNAL_URL=http://localhost:8000/api/v1` (server-only BFF target)
  - Auth calls use same-origin `/api/auth/*`; `NEXT_PUBLIC_API_URL` is only for the product catalog

4. **Tools**:
   - `curl` (CLI for API testing)
   - Browser (Chrome, Firefox, Safari for UI testing)
   - `jq` (optional, for JSON parsing)

### Initial Data Setup

Clear all auth tables before each test run:

```bash
# Connect to PostgreSQL and truncate tables
psql -U postgres -d shopsmart_auth_test -c "TRUNCATE TABLE sessions CASCADE; TRUNCATE TABLE login_attempts CASCADE; TRUNCATE TABLE users CASCADE;"
```

---

## Scenario 1: Happy Path — Registration → Login → Logout

**Objective**: Verify complete user lifecycle (register, log in, access protected resource, log out)

**Expected Duration**: 2 minutes

### Steps

#### 1.1 Register New User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "TestPassword123!"
  }'
```

**Expected Response**: 201 Created

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "testuser@example.com",
  "created_at": "2026-09-15T14:07:39.903Z"
}
```

**Verification**:
- HTTP status is 201
- Response includes user_id, email, created_at
- User record created in database

#### 1.2 Log In with Registered Credentials

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "email": "testuser@example.com",
    "password": "TestPassword123!"
  }'
```

**Expected Response**: 200 OK

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "testuser@example.com"
}
```

**Response Headers**:

```
Set-Cookie: session_id=<uuid>; HttpOnly; Secure; SameSite=Strict; Max-Age=2592000
```

**Verification**:
- HTTP status is 200
- Set-Cookie header present with session_id
- Session record created in database with is_active = TRUE
- LoginAttempt logged with success = TRUE

#### 1.3 Access Protected Resource (Verify Session Works)

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies.txt
```

**Expected Response**: 200 OK

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "testuser@example.com",
  "created_at": "2026-09-15T14:07:39.903Z"
}
```

**Verification**:
- HTTP status is 200
- Response matches logged-in user
- Session.last_activity updated to current time

#### 1.4 Log Out

First retrieve the session-bound CSRF token:

```bash
curl -X GET http://localhost:8000/api/v1/auth/csrf \
  -b cookies.txt
```

Copy the returned `csrf_token` into `CSRF_TOKEN` for the logout request:

```bash
CSRF_TOKEN="<csrf-token-from-response>"
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -b cookies.txt \
  -H "X-CSRF-Token: $CSRF_TOKEN"
```

**Expected Response**: 204 No Content

**Response Headers**:

```
Set-Cookie: session_id=; HttpOnly; Secure; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT
```

**Verification**:
- HTTP status is 204
- Set-Cookie header clears session_id (Max-Age=0)
- Session.is_active set to FALSE in database

#### 1.5 Verify Session is Invalidated

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies.txt
```

**Expected Response**: 401 Unauthorized

```json
{
  "detail": "Unauthorized",
  "status_code": 401,
  "error_code": "unauthorized"
}
```

**Verification**:
- HTTP status is 401
- Access denied after logout
- No session cookie in request succeeds

---

## Scenario 2: Authorization Boundary — Deferred Until a Resource Route Exists

**Status**: Not executable in Feature 001. This feature exposes only the authenticated self-profile endpoint `/api/v1/users/profile`; it does not expose a caller-supplied user ID or any order/cart/document resource route. Do not call the hypothetical `/api/v1/users/{user_id}/profile` path or treat an unimplemented endpoint as a 403 proof. `verify_user_owns_resource()` has unit coverage; route-level owner/non-owner behavior is deferred until a concrete user-owned resource API is approved and implemented.

---

## Scenario 3: Validation — Weak Password Rejected

**Objective**: Verify password strength requirements enforced

**Expected Duration**: 1 minute

### Steps

#### 3.1 Attempt to Register with Weak Password (Too Short)

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weakpass@example.com", "password": "Pass1!"}'
```

**Expected Response**: 400 Bad Request

```json
{
  "detail": "Password must be at least 8 characters with uppercase, lowercase, digit, and special character",
  "status_code": 400,
  "error_code": "weak_password"
}
```

**Verification**: HTTP status is 400; user NOT created

#### 3.2 Attempt to Register with Weak Password (Missing Special Character)

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weakpass2@example.com", "password": "Password1"}'
```

**Expected Response**: 400 Bad Request with weak_password error

**Verification**: HTTP status is 400

#### 3.3 Register with Valid Strong Password (Should Succeed)

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "strongpass@example.com", "password": "StrongPass123!"}'
```

**Expected Response**: 201 Created

**Verification**: HTTP status is 201; user created successfully

---

## Scenario 4: Rate Limiting — Prevent Brute Force

**Objective**: Verify login rate limiting after 5 failed attempts

**Expected Duration**: 2 minutes

### Steps

#### 4.1 Create Test User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ratelimit@example.com", "password": "RateLimit123!"}'
```

#### 4.2 Make 5 Failed Login Attempts from Same IP

```bash
for i in {1..5}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "ratelimit@example.com", "password": "WrongPassword123!"}'
  echo
done
```

**Expected**: Each attempt returns 401 Unauthorized

#### 4.3 Make 6th Login Attempt (Should Be Rate-Limited)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ratelimit@example.com", "password": "WrongPassword123!"}'
```

**Expected Response**: 429 Too Many Requests

```json
{
  "detail": "Too many login attempts. Please try again in 15 minutes.",
  "status_code": 429,
  "error_code": "rate_limited"
}
```

**Verification**:
- HTTP status is 429
- Rate limit enforced after 5 failed attempts
- LoginAttempt records logged for audit

#### 4.4 Correct Password Should Also Be Rate-Limited (Within 15-Minute Window)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ratelimit@example.com", "password": "RateLimit123!"}'
```

**Expected Response**: 429 Too Many Requests (even with correct password)

**Verification**:
- HTTP status is 429
- Rate limiting is IP-based, not account-based (prevents distributed attacks)
- Even correct password is blocked during rate limit window

---

## Scenario 5: Session Timeout — Inactivity Expiration

**Objective**: Verify 30-day inactivity timeout

**Expected Duration**: 5 minutes (with mocked time)

### Steps

#### 5.1 Log In

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies_timeout.txt \
  -d '{"email": "timeout@example.com", "password": "Timeout123!"}'
```

#### 5.2 Verify Session is Active

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies_timeout.txt
```

**Expected Response**: 200 OK

#### 5.3 Simulate 30 Days of Inactivity

Option A: Directly update database

```bash
psql -U postgres -d shopsmart_auth_test -c "
  WITH latest AS (
    SELECT id FROM sessions WHERE is_active = TRUE
    ORDER BY created_at DESC LIMIT 1
  )
  UPDATE sessions
  SET last_activity = NOW() - INTERVAL '31 days'
  WHERE id = (SELECT id FROM latest);
"
```

Option B: Mock time in application (if supported)

```bash
curl -X POST http://localhost:8000/api/v1/test/set-time \
  -H "Content-Type: application/json" \
  -d '{"timestamp": "2026-10-15T14:07:39.903Z"}'  # 30 days later
```

#### 5.4 Attempt Access with Expired Session

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies_timeout.txt
```

**Expected Response**: 401 Unauthorized

```json
{
  "detail": "Unauthorized",
  "status_code": 401,
  "error_code": "unauthorized"
}
```

**Verification**:
- HTTP status is 401
- Session rejected after 30 days inactivity
- User must log in again

---

## Scenario 6: Password Change — Session Invalidation

**Objective**: Verify password change invalidates all sessions

**Expected Duration**: 2 minutes

### Steps

#### 6.1 Log In

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies_pwd.txt \
  -d '{"email": "pwdchange@example.com", "password": "OldPassword123!"}'
```

#### 6.2 Change Password

```bash
# Fetch the session-bound CSRF token after login.
curl -X GET http://localhost:8000/api/v1/auth/csrf \
  -b cookies_pwd.txt

# Copy csrf_token from the response.
CSRF_TOKEN="<csrf-token-from-response>"

curl -X PUT http://localhost:8000/api/v1/users/password \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -b cookies_pwd.txt \
  -d '{
    "current_password": "OldPassword123!",
    "new_password": "NewPassword456!"
  }'
```

**Expected Response**: 204 No Content

#### 6.3 Verify Old Session is Invalidated

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies_pwd.txt
```

**Expected Response**: 401 Unauthorized

**Verification**:
- HTTP status is 401
- Previous session is no longer valid
- User must log in again with new password

#### 6.4 Log In with New Password

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies_new.txt \
  -d '{"email": "pwdchange@example.com", "password": "NewPassword456!"}'
```

**Expected Response**: 200 OK

**Verification**: HTTP status is 200; new session created

---

## Test Automation

### Running All Scenarios via Shell Script

```bash
#!/bin/bash

# Source test utilities
source ./tests/helpers.sh

# Run each scenario
echo "Scenario 1: Happy Path..."
bash ./tests/scenario-1-happy-path.sh
RESULT1=$?

echo "Scenario 2: Authorization Boundary..."
bash ./tests/scenario-2-authorization.sh
RESULT2=$?

echo "Scenario 3: Validation..."
bash ./tests/scenario-3-validation.sh
RESULT3=$?

# ... continue for all scenarios

# Summary
echo
echo "====== TEST RESULTS ======"
[ $RESULT1 -eq 0 ] && echo "✓ Scenario 1: PASS" || echo "✗ Scenario 1: FAIL"
[ $RESULT2 -eq 0 ] && echo "✓ Scenario 2: PASS" || echo "✗ Scenario 2: FAIL"
[ $RESULT3 -eq 0 ] && echo "✓ Scenario 3: PASS" || echo "✗ Scenario 3: FAIL"

exit $(($RESULT1 + $RESULT2 + $RESULT3))
```

---

## Success Criteria

All scenarios pass when:

1. **Scenario 1**: User can register, log in, access protected resource, and log out
2. **Scenario 2**: Cross-user access attempts return 403 Forbidden
3. **Scenario 3**: Weak passwords rejected with 400 Bad Request
4. **Scenario 4**: Rate limiting triggers after 5 failed attempts (429)
5. **Scenario 5**: Session expires after 30 days inactivity (401)
6. **Scenario 6**: Password change invalidates all sessions (401 until new login)

---

## Troubleshooting

### Database Connection Error

```
Error: FATAL: Ident authentication failed for user "postgres"
```

**Fix**: Update `DATABASE_URL` environment variable with correct credentials

### Session Cookie Not Set

```
Set-Cookie header missing from response
```

**Causes**:
- HTTPS not enforced (development can use HTTP but cookie flags may not apply)
- Session creation failed silently (check backend logs)
- Cookie domain mismatch

**Fix**: Check backend logs for errors; ensure HTTPS in production

### Rate Limiting Not Triggering

```
6th login attempt still returns 401, not 429
```

**Causes**:
- Redis not running (if used for rate limiting)
- In-memory rate limiting cleared between requests
- Test requests from different IPs

**Fix**: Verify Redis running; check test IP address (use `127.0.0.1` consistently)

### Session Timeout Not Enforced

```
Access still succeeds after 30 days (mocked)
```

**Causes**:
- Database time not updated correctly
- Session.last_activity still recent
- Test database in different timezone

**Fix**: Verify database time; manually check last_activity timestamp in session table

