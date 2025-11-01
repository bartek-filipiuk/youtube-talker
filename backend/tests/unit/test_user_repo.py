"""
Unit Tests for UserRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.user_repo import UserRepository


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a new user."""
    repo = UserRepository(db_session)
    user = await repo.create(email="newuser@example.com", password_hash="hashed_pw")

    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.password_hash == "hashed_pw"
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession, test_user: User):
    """Test retrieving user by ID."""
    repo = UserRepository(db_session)
    user = await repo.get_by_id(test_user.id)

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(db_session: AsyncSession):
    """Test retrieving non-existent user returns None."""
    from uuid import uuid4

    repo = UserRepository(db_session)
    user = await repo.get_by_id(uuid4())

    assert user is None


@pytest.mark.asyncio
async def test_get_user_by_email(db_session: AsyncSession, test_user: User):
    """Test retrieving user by email."""
    repo = UserRepository(db_session)
    user = await repo.get_by_email(test_user.email)

    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session: AsyncSession):
    """Test retrieving non-existent email returns None."""
    repo = UserRepository(db_session)
    user = await repo.get_by_email("nonexistent@example.com")

    assert user is None


@pytest.mark.asyncio
async def test_delete_user(db_session: AsyncSession, test_user: User):
    """Test deleting a user."""
    repo = UserRepository(db_session)
    result = await repo.delete(test_user.id)

    assert result is True

    # Verify user is deleted
    user = await repo.get_by_id(test_user.id)
    assert user is None


@pytest.mark.asyncio
async def test_user_default_role_and_transcript_count(db_session: AsyncSession):
    """Test that new users get default role='user' and transcript_count=0."""
    repo = UserRepository(db_session)
    user = await repo.create(email="testdefault@example.com", password_hash="hashed")

    assert user.role == "user"
    assert user.transcript_count == 0


@pytest.mark.asyncio
async def test_increment_transcript_count(db_session: AsyncSession, test_user: User):
    """Test incrementing transcript count for a user."""
    repo = UserRepository(db_session)

    # Initial count should be 0
    assert test_user.transcript_count == 0

    # Increment once
    await repo.increment_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == 1

    # Increment again
    await repo.increment_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == 2


@pytest.mark.asyncio
async def test_increment_transcript_count_user_not_found(db_session: AsyncSession):
    """Test incrementing transcript count for non-existent user raises ValueError."""
    from uuid import uuid4

    repo = UserRepository(db_session)

    with pytest.raises(ValueError, match="User .* not found"):
        await repo.increment_transcript_count(uuid4())


@pytest.mark.asyncio
async def test_decrement_transcript_count(db_session: AsyncSession, test_user: User):
    """Test decrementing transcript count for a user."""
    repo = UserRepository(db_session)

    # Set initial count to 5
    await repo.increment_transcript_count(test_user.id)
    await repo.increment_transcript_count(test_user.id)
    await repo.increment_transcript_count(test_user.id)
    await repo.increment_transcript_count(test_user.id)
    await repo.increment_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == 5

    # Decrement once
    await repo.decrement_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == 4

    # Decrement again
    await repo.decrement_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == 3


@pytest.mark.asyncio
async def test_decrement_transcript_count_at_zero(db_session: AsyncSession, test_user: User):
    """Test decrementing transcript count when already at 0 goes to -1 (no constraint)."""
    repo = UserRepository(db_session)

    # Initial count should be 0
    assert test_user.transcript_count == 0

    # Decrement from 0 should go to -1 (there's no constraint preventing negative)
    await repo.decrement_transcript_count(test_user.id)
    await db_session.refresh(test_user)
    assert test_user.transcript_count == -1


@pytest.mark.asyncio
async def test_decrement_transcript_count_user_not_found(db_session: AsyncSession):
    """Test decrementing transcript count for non-existent user raises ValueError."""
    from uuid import uuid4

    repo = UserRepository(db_session)

    with pytest.raises(ValueError, match="User .* not found"):
        await repo.decrement_transcript_count(uuid4())
