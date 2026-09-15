"""Application configuration and settings."""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://user:password@localhost/shopsmart_ai"
    )
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Session
    session_timeout_seconds: int = 30 * 24 * 60 * 60  # 30 days

    # Email
    email_provider: str = os.getenv("EMAIL_PROVIDER", "mock")  # mock | prod
    email_from: str = os.getenv("EMAIL_FROM", "noreply@shopsmart-ai.local")

    # Redis (optional for rate limiting, session cache)
    redis_url: Optional[str] = os.getenv("REDIS_URL", None)

    # API
    api_prefix: str = "/api/v1"
    app_name: str = "ShopSmart AI"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
