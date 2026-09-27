# Backend Development

## Requirements

- Python 3.11 or newer
- PostgreSQL for normal development and PostgreSQL-specific concurrency/persistence checks
- Redis is optional; login rate limiting falls back to process-local memory when Redis is unavailable

## Setup

From the `backend/` directory, create and activate a virtual environment, then install the project and test dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Set `DATABASE_URL` to a PostgreSQL `postgresql+asyncpg://` URL, set a unique non-empty `SECRET_KEY`, and set `CORS_ORIGINS` to a JSON array of exact frontend origins. `REDIS_URL` is optional. Do not commit `.env` or reuse production secrets locally.

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