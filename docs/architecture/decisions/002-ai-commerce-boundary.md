# AI commerce authority boundary

**Status:** Accepted

**Context:** Generated language is useful for interaction but cannot authorize discounts or invent product records.

**Decision:** Route commerce intents to existing services and return structured records. Use RAG/provider generation for stable policy/support evidence. Verify conversation ownership before context access.

**Consequences:** Predictable authority and offline operation; bounded parser coverage requires explicit tests and helpful unsupported-intent behavior.

**Source:** `backend/src/services/assistant_router.py`, `backend/src/services/commerce_assistant.py`, `backend/src/services/ai_governance.py`.
