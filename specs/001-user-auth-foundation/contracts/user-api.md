# User Profile API Contract

**Feature**: User Authentication and Account Foundation

**Version**: 1.0

**Date**: 2026-09-15

## Overview

The User Profile API provides endpoints for authenticated users to view and manage their account information. All endpoints require a valid session cookie and enforce user-scoped authorization (users can only access/modify their own data).

---

## Base URL

```
GET  /api/v1/users/profile
PUT  /api/v1/users/password
```

---

## Endpoints

### 1. Get User Profile

**Endpoint**: `GET /api/v1/users/profile`

**Description**: Retrieve authenticated user's profile information

**Authentication**: Required (session cookie must be valid)

**Authorization**: User can only access their own profile

**Request**: No body

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
| 500 | `fetch_failed` | "Failed to retrieve profile. Please try again." | Server error |

**Side Effects**:
- Session.last_activity updated (extends timeout)

---

### 2. Change Password

**Endpoint**: `PUT /api/v1/users/password`

**Description**: Update authenticated user's password

**Authentication**: Required (session cookie must be valid)

**Authorization**: User can only change their own password

**Request Body**:

```json
{
  "current_password": "OldSecure123!",
  "new_password": "NewSecure456!"
}
```

**Field Validation**:
- `current_password` (string, required): Current password (plain-text, verified against user's hash)
- `new_password` (string, required): New password (≥8 chars, uppercase, lowercase, digit, special char)

**Success Response** (204 No Content):

No response body. User's password is updated and all other sessions are terminated (single-session enforcement: user must log in again on all devices).

**Error Responses**:

| Status | Code | Message | Cause |
|--------|------|---------|-------|
| 400 | `weak_password` | "New password must be at least 8 characters with uppercase, lowercase, digit, and special character" | New password doesn't meet strength requirements |
| 400 | `invalid_current_password` | "Current password is incorrect" | Provided current password doesn't match user's hash |
| 401 | `unauthorized` | "Unauthorized" | Session missing, invalid, or expired |
| 500 | `password_update_failed` | "Failed to update password. Please try again." | Server error |

**Side Effects**:
- User.password_hash updated (bcrypt-hashed with 12 rounds)
- User.updated_at set to NOW()
- All existing sessions for user invalidated (Session.is_active = FALSE)
- Current session is terminated; user must log in again

**Security Note**: On successful password change, the user is effectively logged out. Frontend must redirect to login page after receiving 204 response.

---

## Authorization Rules

### Resource Ownership

Each user-scoped endpoint enforces that the authenticated user can only access their own data.

**Example**: User A attempting to access User B's profile:

```bash
# User A is logged in as user_id = 550e8400-...0000
# User A attempts to GET User B's profile (user_id = 550e8400-...0001)
curl -X GET https://localhost/api/v1/users/550e8400-...0001/profile \
  -b cookies.txt
# Response: 403 Forbidden (cross-user access denied)
```

**Implementation**:
1. Extract user_id from session cookie
2. Extract target_user_id from request (path parameter or resource ownership check)
3. If user_id ≠ target_user_id: Return 403 Forbidden
4. Otherwise: Proceed with request

---

## Common Behaviors

### Session Validation (same as auth endpoints)

All requests validate session:
1. Extract session_id from cookie
2. Verify session is active, not expired (by absolute time or inactivity)
3. If invalid: Return 401 Unauthorized
4. If valid: Update Session.last_activity (extends timeout)

### Error Response Format

Consistent with auth API:

```json
{
  "detail": "Error message text",
  "status_code": 400,
  "error_code": "error_code_string"
}
```

Never expose:
- Stack traces
- Database details
- User's password hash
- Other users' information

### CSRF Protection

State-changing endpoint (PUT /users/password) requires CSRF token:
- Token transmitted in `X-CSRF-Token` header (or body field)
- Token validated server-side before processing request
- Token must match Session.csrf_token (generated at login, stored in session)

---

## Testing Scenarios

### Happy Path: View Profile → Change Password

```bash
# 1. Log in (creates session)
curl -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Secure123!"}' \
  -c cookies.txt
# Response: 200 OK

# 2. View profile
curl -X GET https://localhost/api/v1/users/profile \
  -b cookies.txt
# Response: 200 OK with user_id, email, created_at

# 3. Change password (with CSRF token from login response)
curl -X PUT https://localhost/api/v1/users/password \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <csrf_token>" \
  -b cookies.txt \
  -d '{"current_password": "Secure123!", "new_password": "NewSecure456!"}'
# Response: 204 No Content

# 4. Verify old password doesn't work (session invalidated)
curl -X GET https://localhost/api/v1/users/profile \
  -b cookies.txt
# Response: 401 Unauthorized (session cleared)

# 5. Log in with new password
curl -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "NewSecure456!"}' \
  -c cookies.txt
# Response: 200 OK
```

### Cross-User Access Denied

```bash
# Logged in as User A
curl -X GET https://localhost/api/v1/users/profile \
  -b cookies.txt
# Response: 200 OK (User A's profile)

# User A attempts to access User B's profile (by knowing B's user_id)
# Assuming GET /api/v1/users/{user_id}/profile endpoint exists:
curl -X GET https://localhost/api/v1/users/550e8400-...user-b.../profile \
  -b cookies.txt
# Response: 403 Forbidden
```

### Weak Password Rejection

```bash
curl -X PUT https://localhost/api/v1/users/password \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <csrf_token>" \
  -b cookies.txt \
  -d '{"current_password": "Secure123!", "new_password": "123"}'
# Response: 400 Bad Request with weak_password error
```

### Incorrect Current Password

```bash
curl -X PUT https://localhost/api/v1/users/password \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: <csrf_token>" \
  -b cookies.txt \
  -d '{"current_password": "WrongPassword123!", "new_password": "NewSecure456!"}'
# Response: 400 Bad Request with invalid_current_password error
```

### Session Expired

```bash
# Simulate session expiration (wait 30 days or mock time)
curl -X GET https://localhost/api/v1/users/profile \
  -b cookies.txt
# Response: 401 Unauthorized
```

---

## Integration with Authentication Flow

### After Successful Login

1. Session created with Session.last_activity = NOW()
2. Session cookie set with httpOnly, Secure, SameSite=Strict flags
3. CSRF token generated and stored in Session.csrf_token
4. Frontend stores CSRF token for use in state-changing requests

### On Inactivity

1. If user doesn't make request for 30 days:
   - Session.expires_at < NOW()
   - GET /api/v1/users/profile returns 401 Unauthorized
   - Frontend redirects to login page

### On Password Change

1. User calls PUT /api/v1/users/password with correct current password and new password
2. Backend updates User.password_hash and invalidates all sessions (is_active = FALSE)
3. Current session is terminated; user must log in again
4. Frontend receives 204 and redirects to login page
5. User logs in with new password

