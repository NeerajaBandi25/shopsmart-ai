# AI shopping assistant flow

**Current shopping flow:** Category aliases and 60k-style budgets remain constrained SQL searches. Follow-up buying advice returns `buying_brief` reasons from current price and published specifications, qualifying missing gaming/battery measurements. 'Add the cheaper one' resolves current context before CartService; checkout intent returns `/checkout` for a nonempty cart. Contextual PDP questions search the full product name. These flows share the conventional UI's authority boundary.

**What:** A deterministic intent router selects commerce operations. Conversation context retains product IDs; product cards come from database records.

**Why:** Language is an interface to commerce services. Generated prose does not authorize a price, stock claim, coupon or cart mutation.

**How / request flow:** Authenticated chat → owned conversation lookup → route_assistant_message → catalog/cart/promotion/order service → structured result_data → saved messages → CommerceResults.

**Key files:**

- `backend/src/services/assistant_router.py`
- `backend/src/services/commerce_assistant.py`
- `backend/src/services/ai_repository.py`
- `frontend/src/components/assistant/CommerceResults.tsx`
- `frontend/src/app/assistant/page.tsx`

**Interview talking points:** Separate implemented deterministic commerce operations from external generation. Policy/support answers can use the gateway; shopping cards are hydrated from real records. Test exact supported follow-up phrasing.
