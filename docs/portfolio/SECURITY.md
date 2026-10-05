# Security and privacy

Email-provider logs use constant event messages without recipients, subjects or
bodies. Mock messages remain inspectable in test memory; the production email
provider is still a stub and does not claim real delivery.

Gateway routing takes the highest classification of the declared request and supplied evidence, preventing public snippets from downgrading private input. The comparison tray persists public product IDs only and refreshes displayed facts; it does not persist private orders or use stored prices for checkout. Homepage offers exclude user-private promotions; cart quoting still checks actual eligibility.

This document describes source boundaries, not a penetration-test certification.

Authentication uses bcrypt password hashes and database sessions identified by HttpOnly, Secure, SameSite=Strict cookies. The same-origin proxy preserves the backend Set-Cookie headers. Session validation fails closed and uses a rolling inactivity window. Authenticated mutations require a CSRF token belonging to the exact database session, verified with constant-time comparison.

Authorization derives shopper IDs from session dependencies. Cart, order, conversation and document access must be scoped by that ID. A guessed conversation ID returns an owned-resource failure instead of exposing another shopper's messages.

SQLAlchemy queries use structured predicates. React renders text rather than raw model HTML. Private commerce responses use no-store; login, logout and authentication failures clear the in-memory cart badge.

Promotion privacy is explicit: private coupon eligibility is hidden from other users before timing/status detail is disclosed. Coupon logging uses an HMAC digest. Security events log domain-separated keyed user/client references instead of raw user IDs or IP addresses; arbitrary user-agent text is omitted. The formatter excludes raw user/cart IDs and browser metadata. Pseudonyms still require access and retention controls; server-key rotation breaks historical correlation.

AI tools call validated services. External generation is limited by classification and allowlists; retrieved evidence is untrusted input. These controls reduce prompt-injection impact but do not justify a universal 'injection-proof' claim.

Key files: `backend/src/core/security.py`, `backend/src/api/v1/deps.py`, `backend/src/core/authorization.py`, `backend/src/services/promotion_service.py`, `backend/src/services/ai_repository.py`, `backend/src/services/ai_governance.py`, `backend/tests/integration/test_ai_security.py`.

Verify second-user isolation, missing/wrong CSRF, coupon privacy, checkout replay and hostile discount instructions in the live test run. No payment card data is required.
