# RAG flow

**What:** Curated ShopSmart knowledge is versioned and chunked. A separate user document path retrieves only owned, ready documents.

**Why:** Policies and buying guides change slowly; price, inventory and promotions need live services instead of a vector index.

**How / request flow:** Trusted publish → normalized hash → knowledge version/chunks → active version. Question → embedding → cosine ranking → evidence → gateway → citations or a no-answer response.

**Key files:**

- `backend/src/services/assistant_knowledge.py`
- `backend/src/services/ai_ingestion.py`
- `backend/src/services/ai_retrieval.py`
- `backend/src/services/ai_gateway.py`
- `backend/scripts/publish_knowledge.py`

**Interview talking points:** Explain the difference between shared curated public knowledge and private uploaded documents. Retrieval currently ranks chunks in application memory; an indexed vector store is a future scaling step.
