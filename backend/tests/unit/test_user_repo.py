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
