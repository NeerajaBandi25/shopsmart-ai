# Database model

**Presentation metadata:** `backend/src/schemas/product.py` publishes delivery wording, highlights and up to eight gallery references from `specifications._presentation`. Portfolio variants are separate Product rows with their own ID/SKU/price/stock. The current sibling lookup uses names before the comma; an explicit product-family relation is a future improvement.

**What:** Products carry integer INR minor units, image provenance and structured specifications. Carts belong to users; orders capture historical line values. AI conversations and documents carry ownership.

**Why:** Constraints protect invariants even if an application path has a bug. Historical orders must survive catalog edits.

**How / request flow:** Alembic migrations build the schema. Repositories query it; checkout inserts an order and snapshots its lines inside a durable transaction.

**Key files:**

- `backend/src/models/product.py`
- `backend/src/models/cart.py`
- `backend/src/models/order.py`
- `backend/src/models/promotion.py`
- `backend/src/models/ai.py`
- `backend/migrations/versions`

**Interview talking points:** Explain unique user/idempotency keys, nonnegative stock and totals, and why order product references may become null while the captured name/price remain.
