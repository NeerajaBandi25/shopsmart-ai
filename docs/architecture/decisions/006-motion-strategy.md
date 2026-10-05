# Lightweight accessible motion

**Implemented path:** The current homepage composition uses `frontend/src/components/home/CatalogHero.tsx` and `frontend/src/components/home/CatalogHero.module.css`. Scroll progress drives seven scenes—ask, intent, discovery, comparison, best fit, buy, and release—through CSS custom properties and transform/opacity staging. Scene controls also allow direct selection. Product data comes from the API; product/category destinations and commerce actions remain real links or buttons. Reduced-motion preferences use the static composition.

**Status:** Accepted; browser-validated

**Context:** The hero should communicate discovery without blocking shopping or causing motion discomfort.

**Decision:** Use compatible CSS/React with transform and opacity; retain dimensions and a prefers-reduced-motion static composition. Avoid a large dependency just for decoration.

**Consequences:** A smaller runtime and consistent fallback. Scene controls remain keyboard-operable, and reduced motion is static. Browser checks cover the hero at desktop, tablet, and mobile widths; current verification details are recorded in `.factory/status.md`.

**Source:** `frontend/src/components/home/HomePageExperience.tsx`, `frontend/src/components/home/CatalogHero.tsx`, `frontend/src/components/home/CatalogHero.module.css`.
