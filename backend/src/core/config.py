"""Application configuration and settings."""

import os
import re
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost/shopsmart_ai"
    )
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    # Schema creation is an explicit local/test opt-in; production starts only
    # after the release process has applied Alembic migrations.
    # Let BaseSettings read this per instance; binding os.getenv at import time
    # makes tests and command-local overrides stale after environment changes.
    auto_create_tables: bool = False

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Session
    session_timeout_seconds: int = 30 * 24 * 60 * 60  # 30 days

    # Email
    email_provider: str = os.getenv("EMAIL_PROVIDER", "mock")  # mock | prod
    email_from: str = os.getenv("EMAIL_FROM", "noreply@shopsmart-ai.local")
    public_app_url: str = "http://localhost:3000"

    # Payments remain disabled unless Stripe test-mode credentials are supplied.
    payment_provider: str = "stripe"
    payment_mode: str = "test"
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    payment_success_url: str = "http://localhost:3000/checkout/complete"
    payment_cancel_url: str = "http://localhost:3000/checkout/complete?payment=cancelled"

    # Redis (optional for rate limiting, session cache)
    redis_url: Optional[str] = os.getenv("REDIS_URL", None)
    product_catalog_cache_ttl_seconds: int = Field(default=60, gt=0)

    # API
    api_prefix: str = "/api/v1"
    app_name: str = "ShopSmart AI"
    app_env: str = os.getenv("APP_ENV", "production")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    observability_metrics_token: Optional[str] = None

    # Governed AI provider gateway. External providers remain disabled without their keys.
    ai_provider: str = "deterministic"
    ai_user_documents_enabled: bool = False
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "openai/gpt-4o-mini"
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    # CORS
    cors_origins: list[str] = []
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]

    @field_validator("secret_key")
    @classmethod
    def reject_empty_secret_key(cls, secret_key: str) -> str:
        if not secret_key.strip():
            raise ValueError("SECRET_KEY must not be empty")
        return secret_key

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors_origins(cls, origins: list[str]) -> list[str]:
        """Credentialed CORS requires an explicit allowlist."""
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not contain '*' when credentials are enabled")
        return origins

    @field_validator("observability_metrics_token", mode="before")
    @classmethod
    def validate_observability_metrics_token(cls, token: Optional[str]) -> Optional[str]:
        """Allow metrics to be disabled, but require a strong URL-safe bearer token when set."""
        if token is None or token == "":
            return None
        if not re.fullmatch(r"[A-Za-z0-9._~-]{32,}", token):
            raise ValueError("OBSERVABILITY_METRICS_TOKEN must be at least 32 URL-safe characters")
        return token


settings = Settings()
