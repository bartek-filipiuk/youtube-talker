"""
Authentication Service

Business logic for user registration, login, logout, and session validation.
Uses UserRepository and SessionRepository for database operations.
"""

from datetime import datetime, timedelta
from typing import Dict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, generate_session_token, hash_token
from app.db.models import User
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.session_repo import SessionRepository


class AuthService:
    """
    Business logic for authentication and session management.

    Handles:
    - User registration with email validation and password hashing
    - Login with credential verification and session creation
    - Logout with session deletion
    - Session validation with expiry checking
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize auth service with database session.

        Args:
            db: SQLAlchemy async session for database operations
        """
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    async def register_user(self, email: str, password: str) -> User:
        """
        Register new user with email and password.

        Steps:
        1. Check if email already exists
        2. Hash password securely
        3. Create user in database

        Args:
            email: User email (validated by Pydantic EmailStr)
            password: Plain password (min 8 chars, validated by Pydantic)

        Returns:
            Created User object

        Raises:
            HTTPException(409): Email already registered

        Example:
            >>> user = await auth_service.register_user("test@example.com", "password123")
            >>> user.email
            'test@example.com'
        """
        # Check if email already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=409, detail="Email already registered"
            )

        # Hash password securely
        password_hash = hash_password(password)

        # Create user
        user = await self.user_repo.create(email=email, password_hash=password_hash)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def login(self, email: str, password: str) -> Dict[str, str]:
        """
        Authenticate user and create session.

        Steps:
        1. Verify user exists
        2. Verify password
        3. Generate session token
        4. Store hashed token in database
        5. Return token and user info

        Args:
            email: User email
            password: Plain password

        Returns:
            dict with keys: token, user_id, email

        Raises:
            HTTPException(401): Invalid credentials (wrong email or password)

        Example:
            >>> result = await auth_service.login("test@example.com", "password123")
            >>> result.keys()
            dict_keys(['token', 'user_id', 'email'])
        """
        # Get user by email
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Generate session token
        token = generate_session_token()
        token_hash = hash_token(token)

        # Create session with 7-day expiry
        expires_at = datetime.utcnow() + timedelta(days=7)
        await self.session_repo.create(
            user_id=user.id, token_hash=token_hash, expires_at=expires_at
        )
        await self.db.commit()

        # Return token and user info
        return {"token": token, "user_id": str(user.id), "email": user.email}

    async def logout(self, token: str) -> None:
        """
        Invalidate session (delete from database).

        This is idempotent - succeeds even if token doesn't exist.

        Args:
            token: Session token to invalidate

        Example:
            >>> await auth_service.logout("token_12345")
            # Session deleted if existed
        """
        # Hash token to find session
        token_hash = hash_token(token)
        session = await self.session_repo.get_by_token(token_hash)

        if session:
            await self.session_repo.delete(session.id)
            await self.db.commit()

    async def validate_session(self, token: str) -> User:
        """
        Validate session token and return user.

        Steps:
        1. Hash token and find session
        2. Check if session exists
        3. Check if session expired
        4. Get and return user

        Args:
            token: Session token to validate

        Returns:
            User object if session valid

        Raises:
            HTTPException(401): Invalid session (not found)
            HTTPException(401): Session expired

        Example:
            >>> user = await auth_service.validate_session("valid_token")
            >>> user.email
            'test@example.com'
        """
        # Hash token and find session
        token_hash = hash_token(token)
        session = await self.session_repo.get_by_token(token_hash)

        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")

        # Check if expired
        if session.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Session expired")

        # Get user
        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            # Edge case: user was deleted but session still exists
            raise HTTPException(status_code=401, detail="User not found")

        return user
