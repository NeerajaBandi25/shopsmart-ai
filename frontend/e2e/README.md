# Local browser validation

Use an isolated PostgreSQL review database and a disposable authenticated customer. The suite performs real UI interactions against a running Next.js app and backend; it does not mock commerce responses.

Set `API_INTERNAL_URL` to the backend API root (including `/api/v1`). Set `E2E_ISOLATED_BUILD=1` when building and starting Next.js to keep the browser build in `.next-e2e`, separate from a running developer server. For example, run `npm run build` followed by `npm run start -- --hostname 127.0.0.1 --port 3002` with those environment variables.

Set `E2E_BASE_URL`, `E2E_EMAIL`, and `E2E_PASSWORD` for the running review app. Run `npm run test:e2e`. Install Chromium with `npx playwright install chromium` first; a custom local browser installation can use `PLAYWRIGHT_BROWSERS_PATH`.

Both desktop Chrome and Pixel 7 viewports run the shopping decision, promotion, local adversarial, and preference lifecycle journeys. The mission flow checks an SSE response, recommendation evidence, owner-specific order rendering (including an empty-order account), exact synthetic policy citation, authoritative coupon totals, safe unknown/expired coupon rejection without overwriting the prior valid code, quantity recalculation, coupon removal, and preferences. A separate same-browser account switch verifies cart and coupon state stay isolated between synthetic shoppers. The adversarial flow verifies that secret/SQL/cross-user prompts do not expose sensitive strings or mutate cart/promotion state. Axe checks the assistant's main content. Unexpected console errors, HTTP errors, and horizontal overflow are asserted; the expected 422 responses for the two invalid coupon attempts are counted explicitly. Runtime JSON, failure screenshots and traces are written beneath `.factory/runtime/` and must remain outside source commits.

The default provider may be deterministic for isolated local regression. A passing browser run does not establish adaptive OpenRouter model pinning, live adversarial provider resistance, or Stripe payment validation; run those separately with configured sandbox credentials.
