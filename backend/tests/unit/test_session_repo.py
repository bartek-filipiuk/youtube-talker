"""
Unit Tests for SessionRepository
"""

from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.session_repo import SessionRepository


@pytest.mark.asyncio
async def test_create_session(db_session: AsyncSession, test_user: User):
    """Test creating a new session."""
    repo = SessionRepository(db_session)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    session = await repo.create(
        user_id=test_user.id, token_hash="test_token_hash", expires_at=expires_at
    )

    assert session.id is not None
    assert session.user_id == test_user.id
    assert session.token_hash == "test_token_hash"
    assert session.expires_at == expires_at


@pytest.mark.asyncio
async def test_get_session_by_token(db_session: AsyncSession, test_user: User):
    """Test retrieving session by token hash."""
    repo = SessionRepository(db_session)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    # Create session
    created_session = await repo.create(
        user_id=test_user.id, token_hash="unique_token", expires_at=expires_at
    )

    # Retrieve by token
    session = await repo.get_by_token("unique_token")

    assert session is not None
    assert session.id == created_session.id
    assert session.token_hash == "unique_token"


@pytest.mark.asyncio
async def test_get_session_by_token_not_found(db_session: AsyncSession):
    """Test retrieving non-existent token returns None."""
    repo = SessionRepository(db_session)
    session = await repo.get_by_token("nonexistent_token")

    assert session is None


@pytest.mark.asyncio
async def test_delete_session(db_session: AsyncSession, test_user: User):
    """Test deleting a session."""
    repo = SessionRepository(db_session)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    # Create session
    session = await repo.create(
        user_id=test_user.id, token_hash="delete_me", expires_at=expires_at
    )

    # Delete session
    result = await repo.delete(session.id)
    assert result is True

    # Verify deleted
    deleted_session = await repo.get_by_id(session.id)
    assert deleted_session is None


@pytest.mark.asyncio
async def test_delete_expired_sessions(db_session: AsyncSession, test_user: User):
    """Test deleting expired sessions."""
    repo = SessionRepository(db_session)

    # Create expired session
    expired_time = datetime.now(timezone.utc) - timedelta(days=1)
    await repo.create(
        user_id=test_user.id, token_hash="expired_token", expires_at=expired_time
    )

    # Create valid session
    valid_time = datetime.now(timezone.utc) + timedelta(days=7)
    valid_session = await repo.create(
        user_id=test_user.id, token_hash="valid_token", expires_at=valid_time
    )

    # Delete expired
    deleted_count = await repo.delete_expired()

    assert deleted_count == 1

    # Verify expired session deleted but valid one remains
    expired = await repo.get_by_token("expired_token")
    valid = await repo.get_by_token("valid_token")

    assert expired is None
    assert valid is not None
    assert valid.id == valid_session.id
