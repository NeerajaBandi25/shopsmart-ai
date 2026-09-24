"""Integration tests for process health and database readiness probes."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError


async def test_health_is_database_independent_and_requires_no_auth(
    test_client: AsyncClient, monkeypatch
):
    from src import main

    def unavailable_connection():
        @asynccontextmanager
        async def connection():
            raise OperationalError("SELECT 1", {}, OSError("database secret details"))
            yield

        return connection()

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=unavailable_connection))

    for _ in range(3):
        response = await test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


async def test_readiness_returns_ready_when_database_is_reachable(
    test_client: AsyncClient, test_engine, monkeypatch
):
    from src import main

    monkeypatch.setattr(main, "engine", test_engine)

    checkouts = 0
    checkins = 0

    def on_checkout(*_args):
        nonlocal checkouts
        checkouts += 1

    def on_checkin(*_args):
        nonlocal checkins
        checkins += 1

    event.listen(test_engine.sync_engine, "checkout", on_checkout)
    event.listen(test_engine.sync_engine, "checkin", on_checkin)

    for _ in range(3):
        response = await test_client.get("/readiness")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    assert checkouts == checkins == 3


async def test_readiness_fails_safely_when_database_is_unavailable(
    test_client: AsyncClient, monkeypatch
):
    from src import main

    def unavailable_connection():
        @asynccontextmanager
        async def connection():
            raise OperationalError("SELECT 1", {}, OSError("database secret details"))
            yield

        return connection()

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=unavailable_connection))

    response = await test_client.get("/readiness")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service unavailable",
        "status_code": 503,
        "error_code": "DATABASE_UNAVAILABLE",
    }
    assert "database secret details" not in response.text
    assert "SELECT 1" not in response.text
    assert "Traceback" not in response.text