# ShopSmart Portfolio Readiness

**Updated**: 2026-10-03
**Checkout**: `feature/promotions-discount-engine`
**Portfolio ready**: NO

## Guardrails

- Local synthetic data only; do not deploy or merge to a protected branch.
- The only authorized database is loopback `shopsmart_portfolio`; never connect to `shopsmart_ai`.
- Preserve the dirty worktree and existing records. No reset, reseed, commit, or push.
- The app uses the dedicated local ports 8001 (backend) and 3001 (frontend).

## Verified State

| Workstream | Status | Evidence |
|---|---|---|
| Database and catalog | VERIFIED | Read-only query to `shopsmart_portfolio`: 1,200 products, 1,200 image URLs, Alembic revision `017_order_delivery_images`. Product art is repository-generated; `frontend/public/images/products/portfolio/manifest.json` records generator provenance and asset hashes. `image_license_url` is empty because the art is internal, not externally licensed. |
| Storefront and product detail | PARTIAL | Live catalog route returns 1,200 results with INR prices, merchandising metadata, product links, and loaded local illustrations. Filter/detail acceptance and trustworthy responsive captures remain open. |
| Cart, checkout, order history | JOURNEY VERIFIED | A prior live synthetic checkout persisted the India delivery address and immutable product image snapshot; order history showed the saved order. Automated checkout/cart/order tests pass. |
| Shopping assistant | JOURNEY VERIFIED | Live INR search returned eight matching products and add-to-cart succeeded. Unsupported return-policy content correctly fell back without a citation. Assistant result cards still need product imagery review. |
| Backend quality | PASS | Full backend suite: 282 passed, 6 skipped, 1 Pydantic deprecation warning. The SQLite run explicitly skips PostgreSQL row-lock/persistence proofs. |
| Frontend quality | PASS | `tsc --noEmit`; Jest 24 suites/138 tests; Next lint; optimized production build all passed. |
| Browser evidence | BLOCKED | The embedded browser reports the requested Playwright viewport but renders its live document at the host pane width (for example, viewportSize 1440 while `window.innerWidth` is 706). Captures produced in this state are invalid and must not be used as responsive evidence. |
| Accessibility, security, performance, independent critique | OPEN | Complete keyboard/focus, reduced-motion, contrast, security-log, performance, and post-implementation critic checks. |

## Remaining Readiness Gates

1. Obtain reliable screenshots at 390x844, 768x1024, 1024x768, and 1440x900 using a browser whose rendered CSS viewport matches the requested size.
2. Run and record the complete 14-journey acceptance set, including search/filter/PDP, promotions, cart, checkout, orders, and assistant behavior.
3. Complete accessibility, security-log, performance, and independent visual reviews; capture findings and fixes.
4. Update the portfolio evidence index and product audit only after the checks above produce valid evidence.

Do not mark this project portfolio-ready until every gate is complete and verified.