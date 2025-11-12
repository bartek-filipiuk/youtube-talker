"""
Integration Tests for Admin User Management Endpoints

Tests admin-only user management operations including password reset.
Uses FastAPI TestClient to simulate API calls with admin authentication.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Session
from app.core.security import hash_password, hash_token, generate_session_token, verify_password


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """
    Fixture to create a test admin user with hashed password.

    Password for this user is "adminpassword".

    Args:
        db_session: Database session fixture

    Returns:
        User: Test admin user instance with role='admin'
    """
    admin_user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpassword"),
        role="admin"
    )
    db_session.add(admin_user)
    await db_session.flush()
    await db_session.refresh(admin_user)
    await db_session.commit()
    return admin_user


@pytest_asyncio.fixture
async def test_admin_session(db_session: AsyncSession, test_admin_user: User) -> dict:
    """
    Fixture to create a test session for the test admin user.

    Returns:
        dict: Dictionary with 'token' (raw token) and 'session' (Session object)
    """
    token = generate_session_token()
    token_hash = hash_token(token)

    session = Session(
        user_id=test_admin_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.flush()
    await db_session.refresh(session)
    await db_session.commit()

    return {"token": token, "session": session}


@pytest_asyncio.fixture
async def test_regular_user(db_session: AsyncSession) -> User:
    """
    Fixture to create a second regular user for testing password reset.

    Password for this user is "userpassword".

    Args:
        db_session: Database session fixture

    Returns:
        User: Test regular user instance with role='user'
    """
    user = User(
        email="regularuser@example.com",
        password_hash=hash_password("userpassword"),
        role="user"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


class TestResetUserPassword:
    """Integration tests for admin password reset endpoint."""

    def test_reset_password_success(self, client, db_session, test_admin_session, test_regular_user):
        """Admin can successfully reset another user's password."""
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "generated_password" in data
        assert data["user"]["id"] == str(test_regular_user.id)
        assert data["user"]["email"] == test_regular_user.email
        assert data["user"]["role"] == "user"

        # Verify password format (16 chars with mixed case, digits, punctuation)
        generated_password = data["generated_password"]
        assert len(generated_password) == 16
        assert any(c.isupper() for c in generated_password)
        assert any(c.islower() for c in generated_password)
        assert any(c.isdigit() for c in generated_password)

    def test_reset_password_verifies_new_password_works(
        self, client, db_session, test_admin_session, test_regular_user
    ):
        """Generated password is properly hashed and can be used to login."""
        # Reset password
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 200
        new_password = response.json()["generated_password"]

        # Attempt login with new password
        login_response = client.post(
            "/api/auth/login",
            json={"email": test_regular_user.email, "password": new_password},
        )

        assert login_response.status_code == 200
        assert "token" in login_response.json()

    def test_reset_password_old_password_no_longer_works(
        self, client, db_session, test_admin_session, test_regular_user
    ):
        """After password reset, old password no longer works."""
        old_password = "userpassword"

        # Verify old password works before reset
        login_before = client.post(
            "/api/auth/login",
            json={"email": test_regular_user.email, "password": old_password},
        )
        assert login_before.status_code == 200

        # Reset password
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )
        assert response.status_code == 200

        # Verify old password no longer works
        login_after = client.post(
            "/api/auth/login",
            json={"email": test_regular_user.email, "password": old_password},
        )
        assert login_after.status_code == 401

    def test_reset_password_cannot_reset_own_password(
        self, client, test_admin_user, test_admin_session
    ):
        """Admin cannot reset their own password for security."""
        response = client.post(
            f"/api/admin/users/{test_admin_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 400
        assert "cannot reset your own password" in response.json()["detail"].lower()

    def test_reset_password_user_not_found(self, client, test_admin_session):
        """Resetting password for nonexistent user returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/api/admin/users/{fake_uuid}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_reset_password_non_admin_forbidden(self, client, test_user, test_session, test_regular_user):
        """Non-admin users cannot reset passwords."""
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    def test_reset_password_no_auth_header(self, client, test_regular_user):
        """Reset password without Authorization header returns 401."""
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
        )

        assert response.status_code == 401

    def test_reset_password_invalid_token(self, client, test_regular_user):
        """Reset password with invalid token returns 401."""
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        assert response.status_code == 401

    def test_reset_password_invalid_uuid_format(self, client, test_admin_session):
        """Reset password with invalid UUID format returns 422."""
        response = client.post(
            "/api/admin/users/not-a-uuid/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 422

    def test_reset_password_rate_limiting(self, client, test_admin_session, test_regular_user):
        """Rate limiting prevents more than 10 password resets per minute."""
        # Make 10 requests (should all succeed)
        for _ in range(10):
            response = client.post(
                f"/api/admin/users/{test_regular_user.id}/reset-password",
                headers={"Authorization": f"Bearer {test_admin_session['token']}"},
            )
            # First 10 should succeed
            assert response.status_code == 200

        # 11th request should be rate limited
        response = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 429

    def test_reset_password_generates_unique_passwords(
        self, client, test_admin_session, test_regular_user
    ):
        """Each password reset generates a unique password."""
        # Reset password twice
        response1 = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )
        password1 = response1.json()["generated_password"]

        response2 = client.post(
            f"/api/admin/users/{test_regular_user.id}/reset-password",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )
        password2 = response2.json()["generated_password"]

        # Passwords should be different
        assert password1 != password2


class TestListUsers:
    """Integration tests for admin list users endpoint."""

    def test_list_users_success(self, client, test_admin_session, test_user):
        """Admin can list all users with pagination."""
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "users" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["users"], list)
        assert data["total"] >= 1  # At least the admin user

    def test_list_users_non_admin_forbidden(self, client, test_user, test_session):
        """Non-admin users cannot list all users."""
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 403


class TestCreateUser:
    """Integration tests for admin create user endpoint."""

    def test_create_user_success(self, client, test_admin_session):
        """Admin can create new user with generated password."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
            json={"email": "newuser@example.com"},
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "user" in data
        assert "generated_password" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert len(data["generated_password"]) == 16

    def test_create_user_duplicate_email(self, client, test_admin_session, test_user):
        """Creating user with duplicate email returns 409."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
            json={"email": test_user.email},
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_create_user_non_admin_forbidden(self, client, test_user, test_session):
        """Non-admin users cannot create users."""
        response = client.post(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {test_session['token']}"},
            json={"email": "newuser@example.com"},
        )

        assert response.status_code == 403


class TestDeleteUser:
    """Integration tests for admin delete user endpoint."""

    def test_delete_user_success(self, client, test_admin_session, test_regular_user):
        """Admin can delete another user."""
        response = client.delete(
            f"/api/admin/users/{test_regular_user.id}",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 204

    def test_delete_user_cannot_delete_self(self, client, test_admin_user, test_admin_session):
        """Admin cannot delete their own account."""
        response = client.delete(
            f"/api/admin/users/{test_admin_user.id}",
            headers={"Authorization": f"Bearer {test_admin_session['token']}"},
        )

        assert response.status_code == 400
        assert "cannot delete your own account" in response.json()["detail"].lower()

    def test_delete_user_non_admin_forbidden(self, client, test_user, test_session, test_regular_user):
        """Non-admin users cannot delete users."""
        response = client.delete(
            f"/api/admin/users/{test_regular_user.id}",
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 403
