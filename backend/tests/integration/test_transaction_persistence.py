"""PG-backed transaction-persistence proofs for D1/D2/D5.

Proves with fresh, independent PostgreSQL sessions (new AsyncSession per
request + separate validation session):
  - failed login attempt persisted (D1)
  - successful login attempt persisted (D2)
  - 6th failed attempt returns 429 across separate requests/sessions (D1)
  - logout invalidation visible from a fresh session + /auth/me -> 401 (D5)

Skips gracefully when PostgreSQL is unavailable. SQLite tests are NOT used
as proof of PG transaction/locking behavior.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _pg_test_url() -> str:
    from src.core.config import settings

    db_url = settings.database_url
    if "_test" not in db_url:
        parts = db_url.rsplit("/", 1)
        if len(parts) == 2:
            db_url = f"{parts[0]}/{parts[1]}_test"
    return db_url.replace("@localhost", "@127.0.0.1")


def _pg_available(url: str) -> bool:
    return url.startswith("postgresql")


@pytest_asyncio.fixture
async def pg_engine():
    """Create a PostgreSQL engine for persistence proofs; skip if unavailable."""
    url = _pg_test_url()
    if not _pg_available(url):
        pytest.skip("PostgreSQL DATABASE_URL not configured; skipping PG proofs")
    try:
        engine = create_async_engine(url, echo=False)
        async with engine.connect():
            pass
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    from src.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_factory(pg_engine):
    return sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def pg_user(pg_factory):
    """Create one user via an independent setup session."""
    from src.core.security import hash_password
    from src.repositories.user_repository import UserRepository

    email = "persist@example.com"
    password = "Persist123!"
    async with pg_factory() as session:
        repo = UserRepository(db=session)
        await repo.create_user(email=email, password_hash=hash_password(password))
        await session.commit()
    return {"email": email, "password": password}


@pytest_asyncio.fixture
async def pg_client(pg_factory) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client whose get_db yields a fresh, independent session per request."""
    from src.api.v1.deps import get_db
    from src.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with pg_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    original_override = app.dependency_overrides.get(get_db)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def test_lifespan(app):
        yield

    app.dependency_overrides[get_db] = override_get_db
    app.router.lifespan_context = test_lifespan
    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_override
        app.router.lifespan_context = original_lifespan


class TestTransactionPersistence:
    async def test_failed_login_attempt_persisted(self, pg_client, pg_user, pg_factory):
        """D1: failed login LoginAttempt visible from a fresh session."""
        resp = await pg_client.post(
            "/api/v1/auth/login",
            json={"email": pg_user["email"], "password": "Wrong123!x"},
        )
        assert resp.status_code == 401

        from src.models.login_attempt import LoginAttempt

        async with pg_factory() as check:
            result = await check.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == pg_user["email"],
                    LoginAttempt.success == False,  # noqa: E712
                )
            )
            assert len(result.scalars().all()) >= 1

    async def test_successful_login_attempt_persisted(self, pg_client, pg_user, pg_factory):
        """D2: successful login LoginAttempt visible from a fresh session."""
        resp = await pg_client.post("/api/v1/auth/login", json=pg_user)
        assert resp.status_code == 200

        from src.models.login_attempt import LoginAttempt

        async with pg_factory() as check:
            result = await check.execute(
                select(LoginAttempt).where(
                    LoginAttempt.email == pg_user["email"],
                    LoginAttempt.success == True,  # noqa: E712
                )
            )
            assert len(result.scalars().all()) >= 1

    async def test_sixth_failed_attempt_returns_429(self, pg_client):
        """D1: 6th failed attempt returns 429 across separate requests/sessions."""
        payload = {"email": "ratelimit@example.com", "password": "Wrong123!x"}
        for _ in range(5):
            resp = await pg_client.post("/api/v1/auth/login", json=payload)
            assert resp.status_code == 401
        resp = await pg_client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 429

    async def test_logout_visible_from_fresh_session(self, pg_client, pg_user, pg_factory):
        """D5: logout invalidation committed; fresh session sees it, /me -> 401."""
        login = await pg_client.post("/api/v1/auth/login", json=pg_user)
        assert login.status_code == 200
        cookies = login.cookies
        session_id = cookies.get("session_id")
        assert session_id
        request_cookies = {"session_id": session_id}
        csrf_response = await pg_client.get(
            "/api/v1/auth/csrf", cookies=request_cookies
        )
        assert csrf_response.status_code == 200

        logout = await pg_client.post(
            "/api/v1/auth/logout",
            cookies=request_cookies,
            headers={"X-CSRF-Token": csrf_response.json()["csrf_token"]},
        )
        assert logout.status_code == 204

        from src.repositories.session_repository import SessionRepository

        async with pg_factory() as check:
            repo = SessionRepository(db=check)
            session = await repo.get_session(session_id)
            assert session is not None
            assert session.is_active is False

        me = await pg_client.get("/api/v1/auth/me", cookies=cookies)
        assert me.status_code == 401
