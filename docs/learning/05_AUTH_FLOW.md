# Authentication flow

**What:** Passwords are bcrypt hashes. Random session IDs identify database sessions through an HttpOnly cookie. A stored CSRF token protects authenticated mutations.

**Why:** Authentication proves who the shopper is; authorization checks what that shopper owns. Neither comes from user-supplied IDs.

**How / request flow:** Login → AuthService → session row and cookie. Protected request → get_current_user → validate_session. Mutation → require_csrf_token → constant-time comparison with the same session's token.

**Key files:**

- `backend/src/core/security.py`
- `backend/src/services/auth_service.py`
- `backend/src/core/session_validator.py`
- `backend/src/api/v1/deps.py`
- `frontend/src/app/api/auth/_proxy.ts`
- `frontend/src/lib/api-client.ts`

**Interview talking points:** The active CSRF boundary is the database session dependency, not the older in-memory CSRFTokenManager helper. Explain rolling inactivity expiry and secure cookie configuration separately.
