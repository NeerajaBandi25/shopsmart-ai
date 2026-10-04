# Database-backed session and CSRF boundary

**Status:** Accepted

**Context:** The browser needs a persistent login while state-changing requests must be tied to the authenticated shopper.

**Decision:** FastAPI validates the opaque session cookie against the session store and derives the user ID server-side. Authenticated mutations require the CSRF token stored on that same session. The Next.js BFF forwards only the required cookie and CSRF header for each route.

**Consequences:** Browser-supplied user IDs do not establish ownership, and public catalog calls need no session. Session invalidation and CSRF checks use database-backed session state. This is not a claim that all reads require CSRF or that the BFF replaces authorization.

**Source:** `backend/src/api/v1/deps.py`, `backend/src/core/session_validator.py`, `frontend/src/app/api/_commerce-proxy.ts`.
