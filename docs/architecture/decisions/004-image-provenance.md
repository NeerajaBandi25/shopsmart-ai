# Database-driven image provenance

**Portfolio assets:** The 75 photo-style family images were generated for this repository with the built-in image-generation tool and are published as optimized JPEGs. `frontend/public/images/products/portfolio/manifest.json` records each image's brief, receipt, dimensions, bytes and SHA-256; the catalog seed consumes those paths and hashes. After a family-image repair, regenerate metadata and update the disposable database together. Inspect product-to-image correspondence before retaining screenshots.

**Status:** Accepted

**Context:** Images need a traceable source and must correspond to the returned product record.

**Decision:** Persist image URL, alternative text, creator, source, license and SHA-256 alongside products. UI consumes these fields; missing imagery is an explicit fallback state.

**Consequences:** Centralized provenance supports asset review. These images are illustrative family imagery, not proof that a photo depicts the exact fictional SKU; the interface says so. A hash proves identity, not legal rights or visual fidelity. Family-image reuse should be disclosed.

**Source:** `backend/src/models/product.py`, `frontend/src/components/product-detail/ProductGallery.tsx`, `backend/src/seed/portfolio_catalog.py`.
