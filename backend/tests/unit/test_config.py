"""Tests for required application configuration."""

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None)


def test_secret_key_loads_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    configured_settings = Settings(_env_file=None)

    assert configured_settings.secret_key == "test-secret-key"


def test_secret_key_must_not_be_empty(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "  ")

    with pytest.raises(ValidationError, match="must not be empty"):
        Settings(_env_file=None)


def test_cors_origins_parse_json_array_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["https://shop.example.test","https://admin.example.test"]',
    )

    configured_settings = Settings(_env_file=None)

    assert configured_settings.cors_origins == [
        "https://shop.example.test",
        "https://admin.example.test",
    ]


def test_cors_origins_default_to_deny_cross_origin(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    configured_settings = Settings(_env_file=None)

    assert configured_settings.cors_origins == []


def test_wildcard_origin_is_rejected_with_credentials_enabled(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')

    with pytest.raises(ValidationError, match="must not contain"):
        Settings(_env_file=None)