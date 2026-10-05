# How to debug ShopSmart

**What:** A repeatable path for tracing a customer-visible issue across Next.js, FastAPI, PostgreSQL, and AI orchestration.

**Why:** The same symptom can originate in URL state, a BFF contract, an API/service rule, or stored data.

**Flow:** Reproduce the page and exact request in the browser Network panel. Record the route, status, response error code, and request ID. Follow the same ID in `.factory/backend.log`; inspect the corresponding Next.js route and FastAPI service/repository. For catalog discrepancies, compare the UI query with the public products API and the stored product fields. For assistant behavior, inspect the deterministic route, extracted filters, tool result, and evaluation/test case.

**Key files:** `frontend/src/app/api/`, `backend/src/main.py`, `backend/src/core/observability.py`, `backend/src/services/assistant_router.py`, `backend/src/services/commerce_assistant.py`, `.factory/status.md`.

**Important rules:** Start with read-only checks. Use `shopsmart_portfolio` only for local verification, keep `AUTO_CREATE_TABLES=false`, and never use the ignored SQLite file as a fallback. Tests should use isolated fixtures rather than the portfolio database.

**Common failure:** A healthy `/health` only proves the process responds. Check `/readiness` and the configured database separately. If Next.js reports a missing generated chunk after a build, restart the local dev server and retest the route.

**Interview explanation:** Show how request IDs connect browser-visible errors to sanitized backend events and describe one issue traced from API contract to repository filter.
