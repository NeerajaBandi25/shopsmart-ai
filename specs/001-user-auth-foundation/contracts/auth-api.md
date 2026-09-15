# Authentication API Contract

**Feature**: User Authentication and Account Foundation

**Version**: 1.0

**Date**: 2026-09-15

## Overview

The Authentication API provides endpoints for user registration, login, logout, and authenticated user identity retrieval. All endpoints use HTTP over HTTPS with secure session cookies (httpOnly, Secure, SameSite=Strict).

---

## Base URL

```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

---

## Endpoints

### 1. Register User

**Endpoint**: `POST /api/v1/auth/register`

**Description**: Create a new user account

**Authentication**: None required

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "Secure123!"
}
```

**Field Validation**:
- `email` (string, required): Valid RFC 5322 email format
- `password` (string, required): ≥8 characters, must include uppercase, lowercase, digit, special character

**Success Response** (201 Created):

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "created_at": "2026-09-15T14:05:45.605Z"
}
```

**Error Responses**:

| Status | Code | Message | Cause |
|--------|------|---------|-------|
| 400 | `invalid_email` | "Invalid email format" | Email fails RFC 5322 validation |
| 400 | `weak_password` | "Password must be at least 8 characters with uppercase, lowercase, digit, and special character" | Password doesn't meet strength requirements |
| 409 | `email_exists` | "Email already registered" | Email already exists in system |
| 500 | `registration_failed` | "Registration failed. Please try again later." | Server error (no details exposed) |

**Side Effects**:
- Creates User record in database
- Logs LoginAttempt with success = TRUE
- Does NOT create session (user must log in separately)

---

### 2. Login User

**Endpoint**: `POST /api/v1/auth/login`

**Description**: Authenticate user and create session

**Authentication**: None required

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "Secure123!"
}
```

**Field Validation**:
- `email` (string, required): Email address to authenticate
- `password` (string, required): Plain-text password (transmitted over HTTPS only)

**Success Response** (200 OK):

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com"
}
```

**Set-Cookie Header** (automatic, not visible in response body):

```
Set-Cookie: session_id=550e8400-e29b-41d4-a716-446655440001; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=2592000
```

**Cookie Fields**:
- `HttpOnly`: Prevents JavaScript access (security)
- `Secure`: Transmitted only over HTTPS
- `SameSite=Strict`: Prevents CSRF attacks
- `Max-Age=2592000`: 30 days (matches session expiry in database)

**Error Responses**:

| Status | Code | Message | Cause |
|--------|------|---------|-------|
| 401 | `invalid_credentials` | "Invalid email or password" | Email not found or password incorrect (generic message, no hint) |
| 429 | `rate_limited` | "Too many login attempts. Please try again in 15 minutes." | More than 5 failed attempts from IP in last 15 minutes |
| 500 | `login_failed` | "Login failed. Please try again later." | Server error |

**Side Effects**:
- Logs LoginAttempt with success = TRUE or FALSE
- If successful: Creates Session record, sets session cookie
- If rate-limited: LoginAttempt logged but session NOT created
- If email not found or password wrong: Invalidates any previous single-session for this user (single-session enforcement); creates new session

**Single-Session Enforcement**: If user logs in from a new device, any previous session is invalidated immediately.

---

### 3. Logout User

**Endpoint**: `POST /api/v1/auth/logout`

**Description**: Terminate authenticated session and clear cookie

**Authentication**: Required (session cookie must be valid)

**Request Body**: Empty

```json
{}
```

**Success Response** (204 No Content):

No response body

**Response Headers**:

```
Set-Cookie: session_id=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT
```

**Error Responses**:

| Status | Code | Message | Cause |
|--------|------|---------|-------|
| 401 | `unauthorized` | "Unauthorized" | Session missing or invalid |
| 500 | `logout_failed` | "Logout failed. Please try again." | Server error |

**Side Effects**:
- Sets Session.is_active = FALSE (marks session as logged out)
- Clears session cookie (Max-Age=0)
- Any subsequent requests with this session_id are rejected with 401

---

### 4. Get Current User

**Endpoint**: `GET /api/v1/auth/me`

**Description**: Retrieve authenticated user's identity

**Authentication**: Required (session cookie must be valid)

**Request Body**: None

**Success Response** (200 OK):

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "created_at": "2026-09-15T14:05:45.605Z"
}
```

**Error Responses**:

| Status | Code | Message | Cause |
|--------|------|---------|-------|
| 401 | `unauthorized` | "Unauthorized" | Session missing, invalid, or expired |
| 500 | `fetch_failed` | "Failed to retrieve user. Please try again." | Server error |

**Side Effects**:
- Session.last_activity is updated to current time (extends 30-day inactivity timeout)

---

## Common Behaviors

### Session Validation (on every authenticated request)

1. Extract session_id from cookie
2. Look up Session by id in database
3. Verify:
   - Session.is_active = TRUE (not logged out)
   - Session.expires_at > NOW() (not expired by absolute time)
   - NOW() - Session.last_activity < 30 days (not expired by inactivity)
   - Session.user_id references existing User
4. If invalid: Return 401 Unauthorized
5. If valid: Update Session.last_activity = NOW() and continue

### Error Response Format

All error responses use this structure:

```json
{
  "detail": "Error message text",
  "status_code": 400,
  "error_code": "error_code_string"
}
```

**Never expose**:
- Stack traces
- Database query details
- File paths
- Internal service names or versions

### HTTPS & Security

- All endpoints **MUST** be served over HTTPS (no HTTP)
- Session cookies are `Secure` flagged (not sent over HTTP)
- CSRF protection: State-changing endpoints (register, login, logout, password change) require CSRF token in request header or body (or use SameSite=Strict cookie policy)

### Rate Limiting

- **Login endpoint**: Max 5 failed attempts per IP per 15-minute window
- **Registration endpoint**: Max 10 registrations per IP per hour (prevent spam)
- Rate-limit headers (optional but recommended):

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 2
X-RateLimit-Reset: 1694789145
```

### Correlation IDs

Optional but recommended for debugging: Include `X-Request-ID` header in all responses for request tracing.

---

## Testing Scenarios

### Happy Path: Register → Login → Logout

```bash
# 1. Register
curl -X POST https://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Secure123!"}'
# Response: 201 Created

# 2. Login
curl -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Secure123!"}' \
  -c cookies.txt
# Response: 200 OK, Set-Cookie with session_id

# 3. Get current user (uses session cookie)
curl -X GET https://localhost/api/v1/auth/me \
  -b cookies.txt
# Response: 200 OK with user_id, email, created_at

# 4. Logout
curl -X POST https://localhost/api/v1/auth/logout \
  -b cookies.txt
# Response: 204 No Content, Set-Cookie with Max-Age=0

# 5. Verify session is invalid
curl -X GET https://localhost/api/v1/auth/me \
  -b cookies.txt
# Response: 401 Unauthorized
```

### Weak Password Rejection

```bash
curl -X POST https://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "123"}'
# Response: 400 Bad Request with weak_password error
```

### Invalid Credentials

```bash
curl -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "WrongPassword123!"}'
# Response: 401 Unauthorized with invalid_credentials error
```

### Rate Limiting

```bash
# Make 6 failed login attempts from same IP
for i in {1..6}; do
  curl -X POST https://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "user@example.com", "password": "Wrong123!"}'
done
# First 5: 401 Unauthorized
# 6th: 429 Too Many Requests
```

