"""Application configuration and settings."""

import os
import re
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost/shopsmart_ai"
    )
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    auto_create_tables: bool = os.getenv("AUTO_CREATE_TABLES", "True").lower() == "true"

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Session
    session_timeout_seconds: int = 30 * 24 * 60 * 60  # 30 days

    # Email
    email_provider: str = os.getenv("EMAIL_PROVIDER", "mock")  # mock | prod
    email_from: str = os.getenv("EMAIL_FROM", "noreply@shopsmart-ai.local")

    # Redis (optional for rate limiting, session cache)
    redis_url: Optional[str] = os.getenv("REDIS_URL", None)
    product_catalog_cache_ttl_seconds: int = Field(default=60, gt=0)

    # API
    api_prefix: str = "/api/v1"
    app_name: str = "ShopSmart AI"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    observability_metrics_token: Optional[str] = None

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

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
