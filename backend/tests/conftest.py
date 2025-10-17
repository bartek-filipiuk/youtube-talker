"""
Test Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.models import Base, User, Conversation
from app.main import app

# Test database URL (uses different database than dev)
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5435/youtube_talker_test"

# Create test engine with connection pooling disabled for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool  # Disable pooling to avoid connection conflicts
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def client() -> TestClient:
    """
    Fixture for FastAPI TestClient.

    Returns:
        TestClient: Test client for making requests to the API
    """
    return TestClient(app)


@pytest.fixture
def test_env(monkeypatch) -> None:
    """
    Fixture to set test environment variables.

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setenv("ENV", "testing")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:4321,http://localhost:3000")


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Fixture to create test database session.

    Creates all tables before test, yields session, then cleans up.
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            # Close session before dropping tables
            await session.close()

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """
    Fixture to create a test user.

    Args:
        db_session: Database session fixture

    Returns:
        User: Test user instance
    """
    user = User(email="test@example.com", password_hash="hashed_password")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_conversation(db_session: AsyncSession, test_user: User) -> Conversation:
    """
    Fixture to create a test conversation.

    Args:
        db_session: Database session fixture
        test_user: Test user fixture

    Returns:
        Conversation: Test conversation instance
    """
    conversation = Conversation(user_id=test_user.id, title="Test Conversation")
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)
    return conversation
