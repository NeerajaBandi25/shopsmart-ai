# Homepage discovery flow

**What:** The home experience combines bounded merchandising from `/api/v1/products/homepage` with a guided laptop shortlist from `/api/v1/products/hero-shortlist`.

**Why:** The story can demonstrate search, compare, and advice while sourcing names, images, prices, stock, and specifications from active catalog records.

**How / request flow:** Next.js loads same-origin `/api/homepage` and `/api/hero-shortlist` handlers. `HomepageService` selects image-backed shelves and public offer descriptions. `HeroStoryService` filters in-stock laptops under ₹70,000, groups repeated configurations by image, selects up to three candidates, and derives a best-fit reason from published RAM and price. The hero renders selectable scenes; adding the selected item calls the ordinary cart path.

**Key files:**

- `frontend/src/components/home/HomePageExperience.tsx`
- `frontend/src/components/home/CatalogHero.tsx`
- `frontend/src/app/api/homepage/route.ts`
- `frontend/src/app/api/hero-shortlist/route.ts`
- `backend/src/services/homepage_service.py`
- `backend/src/services/hero_story_service.py`

**Interview talking points:** The best-fit wording describes this bounded shortlist rule, not benchmark-tested performance or personalized machine-learning ranking. If no qualifying product data is available, the guided story can be absent; normal catalog browsing remains the source for discovery.
