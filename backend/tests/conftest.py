"""Pytest configuration and shared fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event, CheckConstraint
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import all models to register them with Base before creating fixtures
from src.models.base import Base
from src.models.user import User
from src.models.session import Session
from src.models.login_attempt import LoginAttempt


@event.listens_for(Base.metadata, "before_create")
def filter_sqlite_constraints(target, connection, **kw):
    """Filter out PostgreSQL-specific constraints (e.g. regex operators) when running in-memory SQLite tests."""
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            table.constraints = {
                c
                for c in table.constraints
                if not (isinstance(c, CheckConstraint) and "~" in str(c.sqltext))
            }


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def test_user_data() -> dict:
    """Test user data."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
    }


@pytest_asyncio.fixture
async def test_user_data_in_db(test_db: AsyncSession, test_user_data: dict):
    """Create a test user in the database."""
    from src.repositories.user_repository import UserRepository
    from src.core.security import hash_password

    user_repo = UserRepository(db=test_db)
    await user_repo.create_user(
        email=test_user_data["email"],
        password_hash=hash_password(test_user_data["password"]),
    )
    await test_db.commit()
    return test_user_data


@pytest_asyncio.fixture
async def test_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with test database."""
    # Import here to avoid database init at module load time
    from src.api.v1.deps import get_db
    from src.main import app

    # Override the dependency - return async generator directly
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    # Override lifespan to skip init_db
    @asynccontextmanager
    async def test_lifespan(app):
        yield

    app.router.lifespan_context = test_lifespan

    try:
        async with AsyncClient(app=app, base_url="https://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def mock_email_provider(monkeypatch):
    """Mock email provider for testing."""
    sent_emails = []

    class MockEmailProvider:
        @staticmethod
        def send_notification(recipient: str, subject: str, body: str) -> bool:
            sent_emails.append({
                "recipient": recipient,
                "subject": subject,
                "body": body,
            })
            return True

        @staticmethod
        def get_sent_emails():
            return sent_emails

    return MockEmailProvider()
