# Observability

**What:** Structured JSON logs include validated request IDs and allowlisted context. Bounded counters cover HTTP, security and AI outcomes.

**Why:** A failed checkout should be diagnosable without logging passwords, full prompts or coupon secrets.

**How / request flow:** Request middleware establishes correlation → services emit domain events → formatter outputs JSON → process-local metrics endpoint reports aggregate counters.

**Key files:**

- `backend/src/core/observability.py`
- `backend/src/api/v1/observability_routes.py`
- `backend/OBSERVABILITY.md`
- `backend/tests/integration/test_observability.py`

**Interview talking points:** Correlation connects a browser failure with a backend operation. Security events use keyed, domain-separated user/client references and omit arbitrary user-agent text, keeping exported logs free of raw user IDs/IPs. These references are pseudonymous, not anonymous; key rotation breaks correlation. Current counters are process-local and restart with the process; they are not a distributed monitoring platform.
