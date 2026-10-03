# Deterministic portfolio catalog

**Status:** Accepted

**Context:** A convincing portfolio needs repeatable data without pretending to sell verified real-brand products.

**Decision:** Generate fictional coherent product families with deterministic IDs in the protected shopsmart_portfolio database. Retain seed environment guards and image metadata.

**Consequences:** Reproducible demos and reviewable provenance. Family-level repetitions and generated reviews/specifications are portfolio data, not real customer evidence.

**Source:** `backend/src/seed/portfolio_catalog.py`, `backend/tests/unit/test_portfolio_catalog_seed.py`.
