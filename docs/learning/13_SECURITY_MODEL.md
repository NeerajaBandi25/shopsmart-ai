# Security model

**What:** ShopSmart uses an HttpOnly session cookie, explicit CSRF protection for mutations, owner-scoped services, and classified AI evidence.

**Why:** Browser state and model output can be stale or manipulated. They cannot authorize access or establish commerce facts.

**Flow:** Next.js same-origin handlers forward only required cookies and CSRF headers. FastAPI validates the session and resolves the user. Domain services scope carts, conversations, promotions, and orders to that user; checkout reloads current product and offer data before persisting an order. Provider governance checks the sensitivity of request and retrieved evidence before external processing.

**Key files:** `frontend/src/app/api/_commerce-proxy.ts`, `backend/src/core/session_validator.py`, `backend/src/api/v1/deps.py`, `backend/src/services/cart_service.py`, `backend/src/services/order_service.py`, `backend/src/services/ai_governance.py`.

**Important rules:** Session identity comes from the server. Never trust client prices, stock, coupon eligibility, order IDs, or assistant-generated tool arguments without validation and ownership checks. Keep secrets and raw private prompts out of logs.

**Common failure / debug:** For 401/403 responses, inspect cookie forwarding, CSRF validation, and the service ownership check in that order. Use request IDs and sanitized security events; do not log cookie or bearer values.

**Interview explanation:** Explain how an authenticated request gets its user identity and why an LLM can recommend from product facts but cannot set price or order state.
