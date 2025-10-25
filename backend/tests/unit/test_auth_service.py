"""
Unit Tests for AuthService

Tests authentication business logic with mocked repositories.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from uuid import uuid4

from app.services.auth_service import AuthService
from app.db.models import User, Session
from app.core.security import hash_password
from app.core.errors import AuthenticationError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    """AuthService with mocked repositories."""
    service = AuthService(mock_db)
    service.user_repo = AsyncMock()
    service.session_repo = AsyncMock()
    return service


class TestRegisterUser:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, auth_service, mock_db):
        """Successful user registration."""
        # Mock: email doesn't exist
        auth_service.user_repo.get_by_email.return_value = None

        # Mock: user creation
        user_id = uuid4()
        mock_user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hashed_password",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        auth_service.user_repo.create.return_value = mock_user

        # Register
        user = await auth_service.register_user("test@example.com", "password123")

        # Assertions
        assert user.email == "test@example.com"
        auth_service.user_repo.get_by_email.assert_called_once_with("test@example.com")
        auth_service.user_repo.create.assert_called_once()

        # Verify password was hashed (create called with password_hash)
        call_kwargs = auth_service.user_repo.create.call_args.kwargs
        assert "password_hash" in call_kwargs
        assert call_kwargs["password_hash"].startswith("$2b$")  # bcrypt format

        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, auth_service):
        """Registration fails with duplicate email."""
        # Mock: email exists
        existing_user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hash",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        auth_service.user_repo.get_by_email.return_value = existing_user

        # Should raise 409
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.register_user("test@example.com", "password123")

        assert exc_info.value.status_code == 409
        assert "already registered" in exc_info.value.detail.lower()

        # Should not attempt to create user
        auth_service.user_repo.create.assert_not_called()


class TestLogin:
    """Tests for user login."""

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_db):
        """Successful login creates session."""
        # Mock: user exists
        user_id = uuid4()
        hashed_password = hash_password("password123")
        mock_user = User(
            id=user_id,
            email="test@example.com",
            password_hash=hashed_password,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        auth_service.user_repo.get_by_email.return_value = mock_user

        # Login
        result = await auth_service.login("test@example.com", "password123")

        # Assertions
        assert "token" in result
        assert result["email"] == "test@example.com"
        assert result["user_id"] == str(user_id)
        assert len(result["token"]) == 64  # 32 bytes hex

        # Verify session was created
        auth_service.session_repo.create.assert_called_once()
        create_kwargs = auth_service.session_repo.create.call_args.kwargs
        assert create_kwargs["user_id"] == user_id
        assert "token_hash" in create_kwargs
        assert "expires_at" in create_kwargs

        # Verify expiry is approximately 7 days from now
        expires_at = create_kwargs["expires_at"]
        expected_expiry = datetime.utcnow() + timedelta(days=7)
        assert abs((expires_at - expected_expiry).total_seconds()) < 5  # Within 5 seconds

        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service):
        """Login fails with wrong password."""
        # Mock: user exists
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash=hash_password("correctpassword"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        auth_service.user_repo.get_by_email.return_value = mock_user

        # Should raise 401
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login("test@example.com", "wrongpassword")

        assert "invalid credentials" in str(exc_info.value).lower()

        # Should not create session
        auth_service.session_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_service):
        """Login fails for nonexistent user."""
        # Mock: user doesn't exist
        auth_service.user_repo.get_by_email.return_value = None

        # Should raise 401
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login("nonexistent@example.com", "password")

        assert "invalid credentials" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_login_case_sensitive_password(self, auth_service):
        """Login is case-sensitive for password."""
        # Mock: user exists
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            password_hash=hash_password("Password123"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        auth_service.user_repo.get_by_email.return_value = mock_user

        # Should fail with lowercase
        with pytest.raises(AuthenticationError):
            await auth_service.login("test@example.com", "password123")


class TestLogout:
    """Tests for user logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_service, mock_db):
        """Successful logout deletes session."""
        # Mock: session exists
        mock_session = Session(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_at=datetime.utcnow(),
        )
        auth_service.session_repo.get_by_token.return_value = mock_session

        # Logout
        await auth_service.logout("some_token")

        # Assertions
        auth_service.session_repo.get_by_token.assert_called_once()
        auth_service.session_repo.delete.assert_called_once_with(mock_session.id)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_invalid_token_idempotent(self, auth_service, mock_db):
        """Logout with invalid token is idempotent (no error)."""
        # Mock: session doesn't exist
        auth_service.session_repo.get_by_token.return_value = None

        # Logout (should not raise error)
        await auth_service.logout("invalid_token")

        # Should not call delete or commit
        auth_service.session_repo.delete.assert_not_called()
        mock_db.commit.assert_not_called()


class TestValidateSession:
    """Tests for session validation."""

    @pytest.mark.asyncio
    async def test_validate_session_success(self, auth_service):
        """Valid session returns user."""
        # Mock: session exists and is valid
        user_id = uuid4()
        mock_session = Session(
            id=uuid4(),
            user_id=user_id,
            token_hash="hashed_token",
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_at=datetime.utcnow(),
        )
        mock_user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hash",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        auth_service.session_repo.get_by_token.return_value = mock_session
        auth_service.user_repo.get_by_id.return_value = mock_user

        # Validate
        user = await auth_service.validate_session("valid_token")

        # Assertions
        assert user.email == "test@example.com"
        assert user.id == user_id
        auth_service.session_repo.get_by_token.assert_called_once()
        auth_service.user_repo.get_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_validate_session_expired(self, auth_service):
        """Expired session raises 401."""
        # Mock: session exists but is expired
        mock_session = Session(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            created_at=datetime.utcnow() - timedelta(days=8),
        )
        auth_service.session_repo.get_by_token.return_value = mock_session

        # Should raise 401
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.validate_session("expired_token")

        assert "expired" in str(exc_info.value).lower()

        # Should not attempt to get user
        auth_service.user_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_session_invalid_token(self, auth_service):
        """Invalid session token raises 401."""
        # Mock: session doesn't exist
        auth_service.session_repo.get_by_token.return_value = None

        # Should raise 401
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.validate_session("invalid_token")

        assert "invalid session" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_session_user_deleted(self, auth_service):
        """Session valid but user deleted raises 401."""
        # Mock: session exists but user doesn't
        mock_session = Session(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.utcnow() + timedelta(days=7),
            created_at=datetime.utcnow(),
        )
        auth_service.session_repo.get_by_token.return_value = mock_session
        auth_service.user_repo.get_by_id.return_value = None  # User deleted

        # Should raise 401
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.validate_session("token_for_deleted_user")

        assert "user not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_session_exactly_at_expiry(self, auth_service):
        """Session exactly at expiry time is considered expired."""
        # Mock: session expires right now
        mock_session = Session(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.utcnow(),  # Expires now
            created_at=datetime.utcnow() - timedelta(days=7),
        )
        auth_service.session_repo.get_by_token.return_value = mock_session

        # Should raise 401 (expired)
        with pytest.raises(AuthenticationError):
            await auth_service.validate_session("expiring_token")
