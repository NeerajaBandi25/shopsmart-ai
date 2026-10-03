# ShopSmart AI Product Audit

**Date**: 2026-10-03
**Checkout**: `feature/promotions-discount-engine`
**Scope**: Read-only baseline review of the running local application. Screens were inspected at 1440x900, 1024x768, and 390x844. A uniquely generated synthetic local account was used for authenticated routes. No migration, reset, seed, or production-data operation was performed.

## Executive Assessment

This assessment records the initial baseline; progress and current browser blockers are recorded below. At baseline, the storefront had a coherent premium visual direction and strong campaign imagery, but presented itself as a design vision rather than a functioning commerce product. The catalog was visibly synthetic, discovery was limited, there was no product detail page, and cart/checkout/order history failed against the local database because it was one migration behind the code. The assistant route loaded, but its result presentation was a plain chat with basic text cards rather than a distinctive shopping experience.

## Implementation Follow-Up

- The public catalog supports search, category/price/stock filters, sorting, pagination totals, active-product detail, and INR prices. The authorized local database is at revision `017_order_delivery_images`.
- A read-only query confirmed 1,200 products, each with a local image URL. The product illustrations are repository-generated original artwork; `frontend/public/images/products/portfolio/manifest.json` records the generator, dimensions, and SHA-256 for each asset. The database's `image_license_url` is empty because there is no external license URL; do not invent one.
- Live catalog inspection returned 1,200 results and loaded product illustrations. A prior synthetic checkout/order-history journey captured delivery details and immutable image snapshots; a live INR assistant query returned eight in-stock results and add-to-cart succeeded.
- Backend suite: 282 passed, 6 skipped under SQLite, with one Pydantic deprecation warning. Frontend checks: TypeScript, all 24 Jest suites/138 tests, lint, and production build passed.
- Responsive screenshots from the embedded browser are not accepted: its requested Playwright viewport can differ from the document's actual CSS viewport. The existing screenshots need replacement by correctly sized captures; accessibility, security-log, performance, and independent visual-review gates also remain open.

## Current Recheck (2026-10-03)

The initial baseline below is historical. The current application is connected to the explicitly authorized `shopsmart_portfolio` database at revision `017_order_delivery_images`; no `shopsmart_ai` connection or database reset was performed. Portfolio readiness remains **NO** until the responsive evidence and review gates above are complete.

## Baseline Evidence (Initial Audit)

- The homepage renders at all three requested viewports without horizontal overflow. The measured document heights are approximately 6,680px at 1440px wide, 6,849px at 1024px, and 13,061px at 390px.
- At 390px, the desktop navigation becomes a narrow vertical list at the upper right; there is no compact menu control.
- The hero is visually cohesive and uses a locally stored campaign image. The homepage has nine locally stored category images, but no product images were found in the catalog cards.
- The homepage contains a 24-item text-only product grid with SKU, name, description, price, stock, quantity input, and add-to-cart action. It has pagination but no visible search, filters, sorting, or result count.
- Public API samples include `DEMO-*` records with fictional descriptions and `SYNTH-EVAL-V1-*` records named `Model ####`; several early products have no category. Product records do not expose brand, rating, reviews, list price, variants, or image fields. The local database contains 1,008 products.
- The nine visual category cards are explicitly inspiration-only and do not navigate to filtered catalog results. No product-detail route is present in the frontend route inventory.
- The homepage calls recommendations, visual search, and trend analysis planned. Its footer says commerce features are planned and “No real commerce,” conflicting with visible cart and order functionality.
- The assistant page offers four prompt chips and a sticky text composer. Product results have name, price, description, stock, and add-to-cart, but no imagery, rating, compare/view action, or contextual recommendation controls.
- The cart, checkout, and order-history pages returned generic 500 error states for the synthetic account. Read-only inspection confirmed `shopsmart_ai` is at `012_product_structured_category` and lacks the `promotions` table required by the checked-out code. Migration 013 also backfills existing order pricing fields; it was not applied during this audit.
- Checkout currently presents a review/submit form without delivery address, delivery choice, or a clear multi-step flow. Cart rows have no thumbnails or save-for-later behavior.
- The account page exposes the internal user UUID as a prominent field and offers password change/sign-out, but no shopping preferences or profile controls.
- An independent static product critique reached the same priority findings: catalog credibility, product discovery/detail, mobile navigation, checkout completeness, and richer assistant shopping actions.

## Audit Findings (Initial Audit)

The `CURRENT` labels in these findings refer to the initial baseline above; use
the current recheck and `.factory/status.md` for present-day implementation state.

### 1. Storefront Positioning and Homepage

**CURRENT**: The fashion campaign hero is visually strong, but authenticated navigation can appear beside signed-out Create Account/Sign In hero actions. Below it are a long product grid, visual-only categories, a planned-capabilities band, a registration CTA, and a footer disclaiming real commerce.

**TARGET**: One truthful, product-led homepage with a clear primary shopping action, current merchandising, usable categories, offers, assistant entry, and consistent authenticated/signed-out navigation.

**GAP**: Product language and page hierarchy describe both a live store and a future design concept. The long editorial composition pushes the actual shopping controls far down, especially on mobile.

**REMEDIATION**: Reconcile all homepage/footer copy with shipped behavior; prioritize search and current products above long-form editorial content; make hero actions route to real shopping/assistant journeys; keep auth CTAs conditional on session state.

**ACCEPTANCE TEST**: At 1440x900, 1024x768, and 390x844, verify one consistent auth state, a working primary shopping action in the first viewport, no planned feature presented as available, and a visible path to catalog and assistant without traversing the full campaign page.

### 2. Catalog, Merchandising, and Product Detail

**CURRENT**: 1,008 local records include demo and evaluation names/descriptions. Cards are text-only, categories are not wired to catalog queries, and the product API lacks common merchandising attributes. There is no product-detail route.

**TARGET**: A credible, image-led catalog with realistic branded titles, category/subcategory, useful specifications, current/list pricing, rating/review count, stock, and safe synthetic imagery. Each product should have a useful detail view.

**GAP**: Repeated `Model ####` names, `DEMO-*` SKUs, and explicitly synthetic copy are customer-visible. Search/filter/sort, result count, product images, ratings, product links, and PDP details are missing. The user mission’s example uses INR while the application formats USD; primary-market currency is unresolved in implementation.

**REMEDIATION**: Establish the primary market and currency from the mission (India/INR is the working assumption); define a stable product presentation contract; curate a realistic, internally synthetic catalog; use repository-owned or otherwise permitted imagery; add responsive search/filter/sort and PDP routes; wire category cards to actual queries.

**ACCEPTANCE TEST**: Search “laptops under ₹60,000,” confirm the result count and every result satisfy category/price/availability filters, open a product detail view, and verify image, title, brand, price, stock, highlights/specifications, and add-to-cart behavior against the API. No customer-facing name or description may say “synthetic,” “fictional,” “demo,” or “Model ####.”

### 3. Responsive Navigation and Page Density

**CURRENT**: No horizontal overflow was measured at the three baseline widths. At 390px, however, links stack vertically in a narrow top-right column. The homepage document is about 13,061px high on mobile.

**TARGET**: A compact, keyboard-operable mobile menu and fast access to search, categories, cart, and assistant, with stable layouts and no accidental long-scroll barrier to products.

**GAP**: The current navigation is a desktop flex row with a small-screen vertical fallback. The product grid and campaign sections make the mobile home unusually long.

**REMEDIATION**: Add a real mobile navigation pattern with focus management and clear cart count; reduce homepage catalog volume and editorial duplication; provide direct catalog/category routes.

**ACCEPTANCE TEST**: At 390x844, open/close navigation with keyboard and touch, reach all primary destinations, verify focus visibility and no overlap, and reach search/results without scrolling through all campaign sections. Repeat at 768x1024, 1024x768, and 1440x900 with no horizontal overflow.

### 4. Cart and Promotions

**CURRENT**: Cart source supports quantity updates, removal, coupon apply/remove, and authoritative quote fields. In the audited local database, the cart returned a generic server error because migration 013 is absent. Cart items have no images or deferred-save option.

**TARGET**: A reliable cart with visual item context, ergonomic quantity/remove/save controls, authoritative offers, clear discount math, and immediate repricing.

**GAP**: The current local app cannot exercise the promotion schema. The interface omits item thumbnails, and the discount experience is not visually prominent. A failure state hides the underlying setup cause behind “Internal server error.”

**REMEDIATION**: Validate migration 013 on a disposable local database before promotion journeys; provide a safe development setup path; add product image/variant context and accessible promotion feedback; retain backend authority for all totals.

**ACCEPTANCE TEST**: With a disposable migrated database and synthetic accounts, add/remove/update a line, apply/check/remove a valid coupon, reject expired/future/unknown/private codes without replacing valid state, and compare subtotal/discount/total at every step to the API response.

### 5. Checkout and Order History

**CURRENT**: Checkout is a single order-submit form and order history returned 500 in the audited DB. No delivery address or delivery selection is collected. Existing implementation passes product IDs, quantities, and coupon code to the server and displays server-returned order totals.

**TARGET**: A clear, safe portfolio checkout with address/delivery representation, authoritative order summary, explicit confirmation, and useful order history. No real payment claim unless a real provider is integrated.

**GAP**: The journey jumps from cart to placing an order, with no destination or fulfillment semantics. Current local schema is not aligned with the checked-out order/promotion model.

**REMEDIATION**: Define a truthful non-payment checkout scope; add validated synthetic delivery/contact input and review/confirmation states; migrate only a disposable local DB; preserve locked server recalculation, idempotency, and immutable snapshots.

**ACCEPTANCE TEST**: Complete checkout with synthetic delivery data; attempt tampered client totals and verify they are ignored; verify stored subtotal, discount, total, and promotion snapshot match server calculation; refresh order history and confirm the immutable amount remains visible.

### 6. AI Shopping Assistant

**CURRENT**: The assistant route loads and routes deterministic commerce intents. Its initial state is a mostly empty chat canvas; product result cards are text-only with a basic Add to cart action. There is no comparison table, contextual follow-up UI, or explicit path to a PDP.

**TARGET**: A distinctive commerce workspace with structured product cards, comparison, grounded recommendations, direct product/cart actions, promotion checks, and helpful loading/error/empty states.

**GAP**: Results do not include image, rating, reason-for-match, compare/view actions, or presentation continuity across follow-up messages. The empty canvas offers only generic chips.

**REMEDIATION**: Preserve typed backend tools as the source of commerce facts; enrich structured result data and UI; add comparison and context-aware actions; show clear tool/loading/error states; keep RAG/model output away from price, availability, and promotion authority.

**ACCEPTANCE TEST**: Ask for laptops under ₹60,000; verify every rendered product against API filters; compare two products; ask a grounded use-case question and distinguish sourced facts from recommendations; add one product; check and apply an offer; ask for a secret discount and verify no invented offer appears.

### 7. Trust, Accessibility, and Operations

**CURRENT**: Registration has labeled fields and visible password requirements. The app uses local structured auth and request IDs. The account page foregrounds a raw internal UUID. Cart/checkout/order failures are generic 500s. The homepage contains no clear delivery/returns/support trust content.

**TARGET**: Consistent customer-facing identity, actionable errors, complete keyboard/touch semantics, meaningful trust information, and runtime visibility without leaking secrets or identifiers.

**GAP**: Internal identifiers are presented as customer account content; the generic error hides migration/setup failure; accessibility has not been validated beyond basic labels and screenshots; no promotion-operation logs have been exercised in a working local schema.

**REMEDIATION**: Replace internal UUID display with a non-sensitive account reference or remove it; use safe actionable local setup errors; audit keyboard/focus/reduced motion/contrast/alt text; inspect logs during real synthetic journeys; keep request IDs and bounded safe promotion metadata only.

**ACCEPTANCE TEST**: Complete registration, browse, assistant, cart, and checkout journeys keyboard-only at desktop and touch at mobile; verify focus, labels, errors, reduced-motion behavior, image alternatives, contrast, and zero horizontal overflow. Inspect logs for request ID, operation, status, duration, eligibility/reason, discount cents, and HMAC reference only; assert absence of raw coupon, user/cart IDs, credentials, cookies, auth headers, keys, and raw prompts.

## Remediation Order

1. Provision a disposable `shopsmart_catalog_demo` database, apply migrations through 014, run the guarded additive seed, and verify the live API without touching `shopsmart_ai`.
2. Source exact-product images with verified licenses and provenance; replace temporary category/unavailable states only when accurate media is available.
3. Re-run listing filters, product detail, cart, checkout, order-history, and assistant journeys against the matching backend; finish fulfillment and assistant comparison gaps.
4. Complete keyboard, accessibility, security, performance, and independent visual review gates before making any portfolio-ready claim.

## Working Commerce Assumptions

- Primary-market presentation is India with INR; persisted prices remain integer paise. This is a working assumption grounded in the mission's ₹60,000 example and should be revisited only if product requirements change.
- Existing product rows remain the orderable catalog items. Merchandising fields are nullable and additive so existing product IDs, SKUs, order references, and historical snapshots remain stable.
- No rating or review count is added or displayed until backed by a real verified source. Synthetic social proof would misrepresent customer experience.
- Product imagery must be individually reviewed and have its source URL, creator, license/version, license URL, and content hash recorded. Recognizable branded devices must not be presented as a different fictional product.
- Checkout remains a local portfolio demonstration without real payment processing. Delivery options and dates must not be claimed until they are represented and validated in the checkout contract.

## Audit Limitations

Promotion behavior and order snapshot display could not be exercised in the local browser because `shopsmart_ai` lacks migration 013. The migration was intentionally not applied during baseline audit because it backfills existing orders. No payment provider or live external AI provider was tested. No production data was accessed.