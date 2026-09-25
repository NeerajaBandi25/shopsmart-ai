"""Focused tests for explicit, credentialed CORS configuration."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from src.core.config import Settings


def create_cors_test_app(origins: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get("/resource")
    async def get_resource():
        return {"ok": True}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["content-type"],
    )
    return app


@pytest.mark.parametrize(
    "origin",
    ["https://shop.example.test", "https://admin.example.test"],
)
async def test_configured_origins_receive_credentialed_cors_headers(origin: str):
    settings = Settings(
        secret_key="test-secret-key",
        cors_origins=["https://shop.example.test", "https://admin.example.test"],
        _env_file=None,
    )
    app = create_cors_test_app(settings.cors_origins)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/resource", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"


async def test_unconfigured_origin_receives_no_cors_permission():
    app = create_cors_test_app(["https://shop.example.test"])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/resource", headers={"Origin": "https://untrusted.example.test"}
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-origin") != "*"