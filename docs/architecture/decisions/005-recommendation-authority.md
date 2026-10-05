# Authoritative discovery and recommendations

**Current implementation:** `backend/src/services/homepage_service.py` makes bounded editorial selections from active image-backed records and interleaves categories. `CommerceAssistantService._buying_advice` explains price and published specifications from current shortlist records. The homepage trending shelf is not a measured popularity metric, and advice does not claim benchmark-backed performance rankings.

**Status:** Accepted boundary; ranking can evolve

**Context:** Recommendation prose must not invent price, availability or specifications.

**Decision:** Resolve candidates through ProductCatalogService and hydrate from active records. Keep eligibility and price constraints deterministic. Explain reasons using available specifications and qualify missing facts.

**Consequences:** Ranking can improve independently of commerce authority. A newest-products slice should not be presented as a personalized recommendation algorithm.

**Source:** `backend/src/services/product_catalog_service.py`, `backend/src/services/commerce_assistant.py`.
