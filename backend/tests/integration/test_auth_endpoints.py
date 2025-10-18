"""
Integration Tests for Authentication Endpoints

Tests the full authentication flow with real database and HTTP requests.
Uses FastAPI TestClient to simulate API calls.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.models import User, Session
from app.core.security import hash_password, hash_token, generate_session_token


class TestRegistration:
    """Integration tests for user registration endpoint."""

    def test_register_success(self, client, db_session):
        """Successful user registration creates user in database."""
        response = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "password123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data  # Should not expose password

    def test_register_duplicate_email(self, client, db_session, test_user):
        """Registration with duplicate email returns 409."""
        response = client.post(
            "/api/auth/register",
            json={"email": test_user.email, "password": "password123"},
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client):
        """Registration with invalid email returns 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )

        assert response.status_code == 422

    def test_register_short_password(self, client):
        """Registration with password < 8 chars returns 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "short"},
        )

        assert response.status_code == 422

    def test_register_rate_limiting(self, client):
        """Rate limiting prevents more than 5 registrations per minute."""
        # Make 5 requests (should all succeed or fail based on email)
        for i in range(5):
            client.post(
                "/api/auth/register",
                json={"email": f"user{i}@example.com", "password": "password123"},
            )

        # 6th request should be rate limited
        response = client.post(
            "/api/auth/register",
            json={"email": "user6@example.com", "password": "password123"},
        )

        assert response.status_code == 429


class TestLogin:
    """Integration tests for login endpoint."""

    def test_login_success(self, client, test_user):
        """Successful login returns token and creates session."""
        response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert len(data["token"]) == 64  # 32 bytes hex
        assert data["email"] == test_user.email
        assert data["user_id"] == str(test_user.id)

    def test_login_wrong_password(self, client, test_user):
        """Login with wrong password returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Login with nonexistent email returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )

        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    def test_login_case_sensitive_password(self, client, test_user):
        """Login password is case-sensitive."""
        response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "TestPassword"},
        )

        assert response.status_code == 401

    def test_login_rate_limiting(self, client, test_user):
        """Rate limiting prevents more than 5 login attempts per minute."""
        # Make 5 login attempts
        for _ in range(5):
            client.post(
                "/api/auth/login",
                json={"email": test_user.email, "password": "wrongpassword"},
            )

        # 6th attempt should be rate limited
        response = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )

        assert response.status_code == 429


class TestLogout:
    """Integration tests for logout endpoint."""

    def test_logout_success(self, client, test_user, test_session):
        """Successful logout removes session from database."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 204
        assert response.content == b""  # No content

    def test_logout_invalid_token(self, client):
        """Logout with invalid token is idempotent (no error)."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        # Should still succeed (idempotent)
        assert response.status_code == 204

    def test_logout_no_auth_header(self, client):
        """Logout without Authorization header returns 401."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 401
        assert "authorization header required" in response.json()["detail"].lower()

    def test_logout_invalid_auth_format(self, client):
        """Logout with invalid Authorization format returns 401."""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "InvalidFormat token123"},
        )

        assert response.status_code == 401


class TestGetCurrentUser:
    """Integration tests for /me endpoint."""

    def test_get_current_user_success(self, client, test_user, test_session):
        """Valid session returns user info."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
        assert "created_at" in data
        assert "password" not in data

    def test_get_current_user_invalid_token(self, client):
        """Invalid session token returns 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401

    def test_get_current_user_no_auth_header(self, client):
        """No Authorization header returns 401."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_get_current_user_expired_session(self, client, test_expired_session):
        """Expired session returns 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {test_expired_session['token']}"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


class TestFullAuthFlow:
    """Integration tests for complete authentication flows."""

    def test_full_registration_login_logout_flow(self, client):
        """Complete flow: register -> login -> access protected -> logout."""
        # Step 1: Register
        register_response = client.post(
            "/api/auth/register",
            json={"email": "flowuser@example.com", "password": "flowpass123"},
        )
        assert register_response.status_code == 201
        user_data = register_response.json()

        # Step 2: Login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "flowuser@example.com", "password": "flowpass123"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        # Step 3: Access protected endpoint
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "flowuser@example.com"

        # Step 4: Logout
        logout_response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_response.status_code == 204

        # Step 5: Verify session invalidated
        me_response_after_logout = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_response_after_logout.status_code == 401

    def test_multiple_sessions_same_user(self, client, test_user):
        """Same user can have multiple active sessions."""
        # Login twice
        login1 = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )
        token1 = login1.json()["token"]

        login2 = client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword"},
        )
        token2 = login2.json()["token"]

        assert token1 != token2

        # Both sessions should work
        me1 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token1}"})
        me2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token2}"})

        assert me1.status_code == 200
        assert me2.status_code == 200

        # Logout from first session
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token1}"})

        # First session should be invalid
        me1_after = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token1}"}
        )
        assert me1_after.status_code == 401

        # Second session should still work
        me2_after = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token2}"}
        )
        assert me2_after.status_code == 200
