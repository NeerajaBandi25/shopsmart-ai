# Lightweight accessible motion

**Implemented path:** The current homepage composition uses `frontend/src/components/home/CatalogHero.tsx` and `frontend/src/components/home/CatalogHero.module.css`. It moves through six user-selected editorial scenes, uses CSS transform/opacity staging, and disables movement under reduced-motion preferences. It selects API-returned products; category/product selections are real links and buttons. Browser evidence covers the hero, reduced motion and responsive widths.

**Status:** Accepted; browser-validated

**Context:** The hero should communicate discovery without blocking shopping or causing motion discomfort.

**Decision:** Use compatible CSS/React with transform and opacity; retain dimensions and a prefers-reduced-motion static composition. Avoid a large dependency just for decoration.

**Consequences:** A smaller runtime and consistent fallback. Scene controls remain keyboard-operable, and reduced motion is static. The browser report records zero horizontal overflow at 1440, 1024 and 390 pixels.

**Source:** `frontend/src/components/home/HomePageExperience.tsx`, `frontend/src/components/home/CatalogHero.tsx`, `frontend/src/components/home/CatalogHero.module.css`.
