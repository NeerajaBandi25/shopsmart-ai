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

The public product catalog caches only successful pages under the `shopsmart:product-catalog:v1` namespace. Keys include the current pagination parameters and a generation token. A successful checkout advances that generation after its stock transaction commits, invalidating every cached page. No product-administration API exists; product edits made directly in the database become visible after the configured TTL. PostgreSQL remains the source of truth, and catalog reads fall back to it when Redis is disabled or unavailable.

Apply migrations and start the API:

```powershell
alembic upgrade head
uvicorn src.main:app --reload
```

The versioned API prefix is `/api/v1`. Authentication routes include registration, login, logout, current-user (`/auth/me`), CSRF (`/auth/csrf`), self-profile (`/users/profile`), and password change (`/users/password`). Logout and password change require the session-bound token returned by `/auth/csrf` in `X-CSRF-Token`.

## Tests and Quality

```powershell
python -m pytest tests/ -q
python -m pytest tests/integration/test_transaction_persistence.py -q
ruff check src tests
black --check src tests
```

The PostgreSQL persistence and lock tests require a PostgreSQL test database; PostgreSQL-only persistence tests skip when PostgreSQL is not configured or available. The ordinary unit and API tests use isolated SQLite fixtures and do not prove PostgreSQL locking behavior. To run a focused test without coverage artifacts, add `-o addopts=''` to the pytest command.