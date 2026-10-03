# ShopSmart completion checkpoint

Updated: 2026-10-04. Branch: `feature/promotions-discount-engine`. Continue on existing draft PR #46.

## Product scope

- The home hero walks through discover → brief → shortlist → comparison → recommendation → purchase. Its default brief searches for laptops under ₹70,000. Candidate selection uses real active, in-stock catalog rows, prices and published specifications; three distinct in-budget options are shown.
- Home merchandising stays compact while the hero combines shelf products with up to 100 in-stock catalog rows. Public offer shelves omit private coupon codes and eligibility.
- Seventy-five generated photo-style family images replace cartoon/illustrative family-slot imagery. Manifest records generation receipts, briefs, dimensions, byte counts and hashes. Product pages identify them as illustrative, not exact-SKU photographs.
- Product configuration and purchase actions are adjacent. Assistant search results show four products initially with expansion; a grounded follow-up recommends from those results. Home, assistant and PDP omit the floating command pill where it would collide with primary interactions; Ctrl-K remains available.
- The dedicated portfolio database repair updated image URLs while preserving product identities, stock and order snapshots.

## Verification

- Frontend: 26 Jest suites / 147 tests pass; lint, TypeScript, Prettier and production build pass.
- Browser: `.factory/verify-browser.cjs` passes all six hero scenes, three-option shortlist assertion, actual assistant catalog results and follow-up advice, desktop/tablet/mobile widths (1440/1024/390) with zero overflow, reduced motion, and axe with zero violations.
- Images: validator confirms 75 photos / 15,592,397 bytes, hashes and provenance.
- Backend: 334 tests pass with 6 PostgreSQL-only tests skipped on isolated in-memory SQLite; one Pydantic deprecation warning. The focused homepage service tests both pass, including the expanded 45-product shelves and three laptop candidates.
- A separate attempt using the configured PostgreSQL test URL reached a database role without permission to create tables in schema `public`; no schema grants were changed. The PostgreSQL locking/persistence checks therefore remain unverified in this environment.
- Current reviewed screenshots are in `docs/portfolio/screenshots/`; canonical home, motion, catalog-mobile, PDP and assistant captures use the final preview build.

## Guardrails

No branch switch, new PR, merge or deployment. Browser review uses disposable synthetic accounts. The portfolio backend/database remain running. The original frontend development server was restored on port 3000 and verified against the live catalog; isolated preview servers were stopped.
