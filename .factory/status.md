# Production completion checkpoint

Updated: 2026-10-04 (Asia/Kolkata). Branch: `feature/promotions-discount-engine`. Existing Draft PR #46 only.

## Current inventory

| Workstream | State | Owner | Summary / evidence | Open item |
|---|---|---|---|---|
| Accepted hero | DONE | Lead | Image-family milestone `b1f8377`; six curated assets; 7 desktop + 4 mobile captures; locked for this mission. | Recheck only for integration regression. |
| Homepage after hero | DONE | Lead / Browser QA | Homepage categories now include imagery selected from active, in-stock catalog products; frontend uses accessible image-led category tiles, with a text fallback only when no catalog image exists. Independent retest loaded all 15 catalog-backed category images on desktop/mobile with no overflow. | None. |
| Catalog / cards | VERIFYING | Catalog / Browser QA | Search/filter/sort/paging and URL state exist in current UI and API. | Validate all requested filters/states, accessibility, error and empty result experience. |
| PDP | VERIFYING | PDP / Browser QA | Gallery, variants, authoritative price/stock, compare and assistant links are implemented. | Verify promotions, related items, mobile and add/buy paths against current API. |
| Compare | DONE | Lead / Browser QA | Added `/compare`: it refreshes 2–3 selected IDs from the catalog API, displays current image/price/stock/specifications in a sticky responsive matrix, highlights differences, and links to the assistant with selected product names. Independent code and visual/mobile reviews report no remaining findings; matrix scroll, remove, difference toggle, and grounded assistant handoff verified. | None in this tranche. |
| Assistant / RAG | DONE | Lead / Browser QA | Fixed query-unit words (`rupees`, `rs`, `inr`) being sent as product-name terms after budget parsing; structured regression covers all three. Independent retest of “Find laptops under 70000 rupees” returns 20 real products, all within budget; rupee-symbol query also returns 20. | Broader provider/RAG evaluation remains outside this local journey review. |
| Cart / checkout / orders | VERIFYING | Commerce / Backend Review | Browser checkout journey and backend ownership/pricing review are recorded. PostgreSQL proofs now cover competing checkouts, one-unit inventory decrement, same-key idempotent replay, persisted catalog-price snapshot, and rollback after a database-triggered order-item failure. | Broader journey and observability checks remain in the factory backlog. |
| Database / observability | VERIFYING | Backend Review | Local `shopsmart_portfolio` was not used in this pass. Fresh disposable `shopsmart_factory_test_20261004_22edd76` on `127.0.0.1:5432` migrated to `017_order_delivery_images`; required product/cart/order/promotion tables verified. Eight targeted PostgreSQL tests passed; test teardown was followed by a clean migration to restore the disposable schema. | Production observability/load validation is outside the local browser pass. |
| Security / privacy | VERIFYING | Backend Review / Lead | Independent inspection found no client-pricing or owner-scope bypass in reviewed cart/promotion/checkout/order/AI paths. Fixed timezone-dependent session expiry and default schema auto-create. | Full independent security matrix and logs review still outstanding. |
| Performance / accessibility | VERIFYING | Lead / Browser QA | Browser first pass: no JS/page/request failures, overflow at 4 viewports across 7 pages, or in-view broken images; forcing lazy loads cleared screenshot-only unloaded images. | Current axe/keyboard/contrast/reduced-motion and perf evidence outstanding. |
| Learning / architecture docs | DONE | Documentation Review | Added a numbered learning index with catalog, security, debugging, homepage, trust, and local-operations modules; ADRs 007–008; corrected backend README; updated hero ADR; reconciled `PROJECT_STATUS.md`. Prettier and local-link validation passed. | None. |
| Targeted production gates | DONE | Lead | **BLACK: PASS** using `backend\.venv\Scripts\python.exe -m black --check src tests` (121 files unchanged); cache redirected to the workspace because the default user cache is not writable. **PostgreSQL: PASS** on fresh disposable DB; the exact six previously skipped tests all executed, plus two checkout proofs; 8 passed, 0 failed, 0 skipped. Ruff and `git diff --check` pass. `alembic check` reports no new upgrade operations. | None for these two gates. |
| Full application completion | VERIFYING | Lead | Previous broad checks remain evidenced: backend SQLite suite 342 passed / 6 PostgreSQL-specific skips; frontend 27 suites / 152 passed; TypeScript, lint, Prettier, production build, browser review, and independent code/docs/visual reviews passed. The skipped PostgreSQL cases are now separately run and passed on real PostgreSQL. | Do not mark the application production-complete based only on these gates; catalog/PDP state coverage, security/privacy matrix, accessibility, performance, and production observability remain in the factory backlog. |

## Active environment

- Frontend: `http://127.0.0.1:3000`.
- Backend: `http://127.0.0.1:8000`; local-only env points at loopback PostgreSQL with `AUTO_CREATE_TABLES=false`.
- No SQLite fallback, reseed, schema mutation, production access, deployment, merge, or new PR.

## Workflow guardrail

Builders do not self-approve. Each substantial change requires independent browser/visual and code review; backend/security and performance checks are added where applicable. Only the lead reconciler marks a workstream DONE after evidence.
