# Backend Development

## Requirements

- Python 3.11 or newer
- PostgreSQL for normal development and PostgreSQL-specific concurrency/persistence checks
- Redis is optional; login rate limiting and product catalog reads retain their database/process-local fallback when Redis is unavailable

## Setup

From the `backend/` directory, create and activate a virtual environment, then install the project and test dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Set `DATABASE_URL` to a PostgreSQL `postgresql+asyncpg://` URL, set a unique non-empty `SECRET_KEY`, and set `CORS_ORIGINS` to a JSON array of exact frontend origins. `REDIS_URL` is optional. `PRODUCT_CATALOG_CACHE_TTL_SECONDS` controls public catalog cache freshness (default 60, must be positive). Do not commit `.env` or reuse production secrets locally.

The public product catalog caches only successful, unfiltered newest-first pages under the `shopsmart:product-catalog:v2` namespace. Keys include pagination parameters and a generation token. A successful checkout advances that generation after its stock transaction commits, making prior cached pages unreachable. Filtered searches bypass the page cache. No product-administration API exists; direct database edits are not covered by checkout invalidation. PostgreSQL remains the source of truth, and catalog reads fall back to it when Redis is disabled or unavailable.

Apply migrations and start the API:

```powershell
alembic upgrade head
uvicorn src.main:app --reload
```

The versioned API prefix is `/api/v1`. Authentication routes include registration, login, logout, current-user (`/auth/me`), CSRF (`/auth/csrf`), self-profile (`/users/profile`), and password change (`/users/password`). Logout and password change require the session-bound token returned by `/auth/csrf` in `X-CSRF-Token`.

## Commerce Assistant Knowledge

`POST /api/v1/ai/chat` is an authenticated commerce assistant. Product, cart, order, and promotion facts come from the existing services; provider/model governance details are not returned to customers. Catalog records include brand and canonical category fields. The assistant does not invent offers or claim unsupported filters. RAG is used for curated ShopSmart policy/support knowledge, not live price or stock. Customer-owned document APIs are hidden from OpenAPI and disabled unless `AI_USER_DOCUMENTS_ENABLED=true` is set in a local, development, or test environment.

Apply the Alembic migrations before starting the updated backend. To publish an approved policy source, create a server-side JSON file with `source_key`, `title`, `category`, and `content`, then explicitly enable the guarded command:

```powershell
$env:SHOPSMART_ALLOW_KNOWLEDGE_PUBLISH = "true"
python scripts/publish_knowledge.py .\approved-policy.json --apply
```

Only publish policy text approved by ShopSmart. The command is not an end-user upload route; it versions and indexes content in the separate backend-owned corpus. Without published source material, policy questions safely return that the information was not found.

## Tests and Quality

```powershell
python -m pytest tests/ -q
python -m pytest tests/integration/test_transaction_persistence.py -q
ruff check src tests
black --check src tests
```

The PostgreSQL persistence and lock tests require a PostgreSQL test database; PostgreSQL-only persistence tests skip when PostgreSQL is not configured or available. The ordinary unit and API tests use isolated SQLite fixtures and do not prove PostgreSQL locking behavior. To run a focused test without coverage artifacts, add `-o addopts=''` to the pytest command.
