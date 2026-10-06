"""Opt-in real Redis/PostgreSQL runtime checks against an isolated validation DB."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.redis_client import close_redis_client, get_redis_client
from src.models.user import User
from src.services.adaptive_model_router import ModelRuntimeState
from src.services.assistant_runtime import MissionRuntimeCache
from src.services.shopper_preferences import ExplicitPreferences, ShopperPreferenceService
from src.services.shopping_mission import extract_shopping_mission

pytestmark = pytest.mark.skipif(
    os.getenv("AI_RUNTIME_LIVE_TEST") != "1",
    reason="Isolated Redis/PostgreSQL runtime opt-in required",
)


@pytest.mark.asyncio
async def test_real_redis_mission_cache_is_scoped_expiring_and_non_authoritative(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/15")
    await close_redis_client()
    owner = uuid4()
    client = get_redis_client()
    before = set([key async for key in client.scan_iter(match="shopsmart:ai:mission:v2:*")])
    try:
        runtime = MissionRuntimeCache()
        first, status = await runtime.extract(
            owner, "laptop under 60k", None, extract_shopping_mission
        )
        assert status == "MISS"
        second, status = await runtime.extract(
            owner, "laptop under 60k", None, extract_shopping_mission
        )
        assert status == "HIT" and first == second
        _, status = await runtime.extract(
            uuid4(), "laptop under 60k", None, extract_shopping_mission
        )
        assert status == "MISS"
        after = set([key async for key in client.scan_iter(match="shopsmart:ai:mission:v2:*")])
        for key in after - before:
            assert 0 < await client.ttl(key) <= 300
            payload = await client.get(key)
            assert "stock_quantity" not in payload and "price_cents" not in payload
    finally:
        after = set([key async for key in client.scan_iter(match="shopsmart:ai:mission:v2:*")])
        if after - before:
            await client.delete(*(after - before))
        await close_redis_client()


@pytest.mark.asyncio
async def test_preferences_persist_across_independent_postgresql_sessions():
    assert (
        "factory_test" in settings.database_url
    ), "Live check requires a disposable validation database"
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = uuid4()
    try:
        async with sessions() as db:
            db.add(
                User(
                    id=owner_id, email=f"runtime-{owner_id}@example.com", password_hash="test-only"
                )
            )
            await db.commit()
            await ShopperPreferenceService(db).replace(
                owner_id, ExplicitPreferences(preferred_brands=["Vellune"])
            )
        async with sessions() as db:
            assert (await ShopperPreferenceService(db).get(owner_id))["explicit"][
                "preferred_brands"
            ] == ["Vellune"]
            await ShopperPreferenceService(db).clear(owner_id)
        async with sessions() as db:
            assert (await ShopperPreferenceService(db).get(owner_id))["explicit"][
                "preferred_brands"
            ] == []
    finally:
        async with sessions() as db:
            await db.execute(delete(User).where(User.id == owner_id))
            await db.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_redis_model_rate_limits_and_circuit_have_bounded_ttls(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/15")
    await close_redis_client()
    model = f"factory-runtime/{uuid4().hex}:free"
    client = get_redis_client()
    state = ModelRuntimeState()
    key = f"ai:model:{model}"
    try:
        for _ in range(3):
            await state.record(model, success=False, status_code=429)
        snapshot = await state.snapshot(model, "PRODUCT_SEARCH")
        assert snapshot["429_rate"] == 1.0
        assert snapshot["failure_rate"] == 1.0
        assert snapshot["circuit_state"] == "open"
        for suffix in (":window", ":429_rate", ":failure_rate", ":circuit_state"):
            ttl = await client.ttl(key + suffix)
            assert 0 < ttl <= 900

        await state.record(model, success=True, latency_ms=37, status_code=200)
        snapshot = await state.snapshot(model, "PRODUCT_SEARCH")
        assert snapshot["circuit_state"] == "closed"
        assert snapshot["latency"] == 37.0

        await state.record_eval(model, "PRODUCT_SEARCH", 0.73)
        independent_state = ModelRuntimeState()
        independent_snapshot = await independent_state.snapshot(model, "PRODUCT_SEARCH")
        assert independent_snapshot["eval_score"] == 0.73
        eval_ttl = await client.ttl(key + ":eval_score:product_search")
        assert 0 < eval_ttl <= 86400
    finally:
        keys = [key async for key in client.scan_iter(match=f"{key}:*")]
        if keys:
            await client.delete(*keys)
        await close_redis_client()
