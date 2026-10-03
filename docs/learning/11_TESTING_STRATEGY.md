# Testing strategy

**Regression focus:** Gateway tests verify declared INTERNAL/PRIVATE/SENSITIVE questions cannot reach a PUBLIC-only provider even when retrieved evidence is public. Product response contract tests must include computed delivery/highlights/gallery fields. Browser review must also exercise command dialogs, gallery focus restoration, comparison re-fetch, sibling configuration navigation and 60k budget constraints.

**What:** Unit tests cover rules, integration tests exercise API/persistence, contracts protect payloads, and evaluations test AI boundaries. Browser checks verify actual product journeys.

**Why:** A passing function test cannot prove a modal traps focus, a mobile hero fits, or a cart flow works across pages.

**How / request flow:** Backend: run the full pytest suite with its configured test database. Frontend: Jest → TypeScript → lint → Prettier → production build. Then run live journeys and inspect viewport screenshots.

**Key files:**

- `backend/tests/unit`
- `backend/tests/integration`
- `backend/tests/contract`
- `backend/tests/evals`
- `backend/tests/conftest.py`
- `frontend/package.json`
- `docs/portfolio/screenshots`
- `.factory/status.md`

**Interview talking points:** Report the current run, skips and duration. Historical baseline counts are not evidence for a changed branch. Ownership, idempotency races, private coupons and prompt-injection refusals are high-value checks.
