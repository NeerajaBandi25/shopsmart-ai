# Backend authoritative pricing

**Status:** Accepted

**Context:** Client prices, inventory and eligibility become stale and can be tampered with.

**Decision:** Cart quotes and checkout use current database products and PromotionService. Store INR as integer minor units. Checkout captures totals and line snapshots after validation.

**Consequences:** Clients submit product IDs and quantities, not trusted totals. More work happens at checkout, but catalog changes cannot silently rewrite historical orders.

**Source:** `backend/src/services/cart_service.py`, `backend/src/services/order_service.py`, `backend/src/models/order.py`.
