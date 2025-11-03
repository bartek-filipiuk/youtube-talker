"""
Unit Tests for Dependencies

Tests for authentication and authorization dependencies.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.dependencies import get_admin_user
from app.core.security import hash_password


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """
    Fixture to create a test admin user.

    Args:
        db_session: Database session fixture

    Returns:
        User: Test admin user instance with role='admin'
    """
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("adminpassword"),
        role="admin"
    )
    db_session.add(admin)
    await db_session.flush()
    await db_session.refresh(admin)
    await db_session.commit()
    return admin


@pytest.mark.asyncio
async def test_get_admin_user_success(test_admin_user: User):
    """Test get_admin_user allows admin users through."""
    result = await get_admin_user(user=test_admin_user)

    assert result == test_admin_user
    assert result.role == "admin"
    assert result.email == "admin@example.com"


@pytest.mark.asyncio
async def test_get_admin_user_forbidden_regular_user(test_user: User):
    """Test get_admin_user rejects regular users with 403."""
    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(user=test_user)

    assert exc_info.value.status_code == 403
    assert "Admin access required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_admin_user_validates_role():
    """Test get_admin_user checks the role field correctly."""
    # Create a user with non-admin role
    fake_user = User(
        email="user@example.com",
        password_hash="hash",
        role="user"
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(user=fake_user)

    assert exc_info.value.status_code == 403
