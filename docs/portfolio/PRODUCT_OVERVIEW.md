# ShopSmart AI product overview

The home page now tells a six-step shopping story: discovery, brief, live shortlist, published-data comparison, a qualified recommendation, and purchase. The default brief searches the catalog for laptops under ₹70,000; the hero uses current in-stock products, prices and published specifications. Its initial pool includes homepage shelves and up to 100 catalog rows, while the visible merchandise shelves stay compact. `HomepageService` interleaves categories into editorial selections rather than measured sales popularity or personalized ranking.

Shopping tools include Ctrl/Cmd+K search/AI entry, a three-product comparison tray and contextual PDP AI. Product pages expose API-authored highlights, delivery wording and gallery references. Configuration choices navigate between real sibling SKU records, each with its own stock and price.

The assistant supports category aliases, budget shorthand such as 60k, comparison, a fact-based buying brief, cheaper-item cart actions, offers/coupons and navigation into real checkout. It qualifies missing gaming benchmarks and battery evidence. Ratings and customer-review evidence are not fabricated to fill the interface.

ShopSmart is a portfolio commerce application with a Next.js storefront, FastAPI services, PostgreSQL catalog and orders, and a conversational shopping interface.

The customer journey connects catalog discovery, product detail, cart, promotions, checkout and order history. Product cards and images use product API records. Prices use integer INR minor units and are formatted for display in the frontend.

The portfolio catalog is fictional and generated deterministically by `backend/src/seed/portfolio_catalog.py`. Its intended database is `shopsmart_portfolio`; the seed protects against unintended environments. The 75 photo-style product-family images are generated for this repository, with provenance, generation briefs and hashes recorded in the manifest. They are illustrative family images, not verified photos of exact SKU configurations.

Read `docs/learning/01_PROJECT_MAP.md` for a short source tour and `INTERVIEW_DEMO.md` for the demonstration.

Evidence belongs in `.factory/status.md` and `docs/portfolio/screenshots/`. A source review does not establish visual completion, a particular live product count, successful browser journeys or production readiness. This application does not process real payments.
