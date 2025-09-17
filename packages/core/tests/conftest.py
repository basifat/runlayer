"""
Pytest configuration and fixtures for RunLayer Core API tests.
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.database import Base, get_db
from src.config import settings


# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a test database session."""
    # Create test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    TestSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session
    
    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db):
    """Create a test client with database dependency override."""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return {
        "JWT_SECRET_KEY": "test-secret-key-at-least-32-characters-long",
        "ENVIRONMENT": "testing",
        "DEBUG": True,
        "RATE_LIMIT_REQUESTS_PER_MINUTE": 1000,  # High limits for testing
        "RATE_LIMIT_REQUESTS_PER_HOUR": 10000,
        "REDIS_URL": "redis://localhost:6379/15"  # Test Redis DB
    }
