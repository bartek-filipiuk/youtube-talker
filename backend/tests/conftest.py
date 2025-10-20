"""
Test Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.models import Base, User, Conversation, Session
from app.main import app
from app.db.session import get_db
from app.core.security import hash_password, generate_session_token, hash_token
from datetime import datetime, timedelta
from typing import AsyncGenerator

# Test database URL (uses different database than dev)
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5435/youtube_talker_test"

# Create test engine with connection pooling disabled for tests
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool  # Disable pooling to avoid connection conflicts
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override get_db dependency to use test database."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """
    Setup and teardown test database for each test function.

    This fixture runs automatically before each test to ensure clean database state.
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    Fixture for FastAPI TestClient with test database.

    Returns:
        TestClient: Test client for making requests to the API
    """
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


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
    Fixture to create a test user with hashed password.

    Password for this user is "testpassword".

    Args:
        db_session: Database session fixture

    Returns:
        User: Test user instance
    """
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword")
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_session(db_session: AsyncSession, test_user: User) -> dict:
    """
    Fixture to create a test session for the test user.

    Returns:
        dict: Dictionary with 'token' (raw token) and 'session' (Session object)
    """
    token = generate_session_token()
    token_hash = hash_token(token)

    session = Session(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.flush()
    await db_session.refresh(session)
    await db_session.commit()

    return {"token": token, "session": session}


@pytest_asyncio.fixture
async def test_expired_session(db_session: AsyncSession, test_user: User) -> dict:
    """
    Fixture to create an expired test session for the test user.

    Returns:
        dict: Dictionary with 'token' (raw token) and 'session' (Session object)
    """
    token = generate_session_token()
    token_hash = hash_token(token)

    session = Session(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
    )
    db_session.add(session)
    await db_session.flush()
    await db_session.refresh(session)
    await db_session.commit()

    return {"token": token, "session": session}


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
    await db_session.commit()
    return conversation
