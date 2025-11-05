"""
Authentication API Endpoints

Provides REST endpoints for user registration, login, logout, and session validation.
Rate limiting applied to prevent abuse.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.db.models import User
from app.db.repositories.user_repo import UserRepository
from app.dependencies import get_current_user
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
)
from app.services.auth_service import AuthService

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register new user account and create session (auto-login).

    Rate limit: 5 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        body: Registration data (email, password)
        db: Database session

    Returns:
        TokenResponse with session token and user info (auto-login)

    Raises:
        HTTPException(409): Email already registered
        HTTPException(422): Invalid email or password too short
        HTTPException(429): Rate limit exceeded

    Example:
        >>> POST /api/auth/register
        >>> {"email": "user@example.com", "password": "securepass123"}
        >>> Response: {"token": "...", "user_id": "...", "email": "user@example.com"}
    """
    auth_service = AuthService(db)
    # Create user
    user = await auth_service.register_user(body.email, body.password)
    # Auto-login: create session and return token
    result = await auth_service.login(body.email, body.password)
    return TokenResponse(**result)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and create session.

    Rate limit: 5 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        body: Login credentials (email, password)
        db: Database session

    Returns:
        TokenResponse with session token and user info

    Raises:
        HTTPException(401): Invalid credentials
        HTTPException(429): Rate limit exceeded

    Example:
        >>> POST /api/auth/login
        >>> {"email": "user@example.com", "password": "securepass123"}
        >>> Response: {"token": "...", "user_id": "...", "email": "user@example.com"}
    """
    auth_service = AuthService(db)
    result = await auth_service.login(body.email, body.password)
    return TokenResponse(**result)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Logout user and invalidate session.

    Idempotent operation - succeeds even if token doesn't exist.

    Args:
        request: FastAPI request (contains Authorization header)
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        AuthenticationError: No Authorization header provided or invalid format

    Example:
        >>> POST /api/auth/logout
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationError("Authorization header required")

    # Parse Bearer token
    try:
        parts = auth_header.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Header must have exactly 2 parts")
        scheme, token = parts
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise AuthenticationError("Invalid Authorization header format. Use: Bearer <token>")

    # Logout (idempotent - doesn't fail if token doesn't exist)
    auth_service = AuthService(db)
    await auth_service.logout(token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        user: Current authenticated user (from dependency)

    Returns:
        UserResponse with user info

    Raises:
        HTTPException(401): Invalid, expired, or missing session token

    Example:
        >>> GET /api/auth/me
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {"id": "...", "email": "user@example.com", "created_at": "..."}
    """
    return UserResponse.model_validate(user)


@router.post("/change-password", status_code=200)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Change authenticated user's password.

    Requires old password verification for security.
    Rate limit: 5 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        body: Password change data (old_password, new_password)
        user: Current authenticated user (from dependency)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException(401): Invalid old password or missing auth token
        HTTPException(422): New password too short (min 8 chars)
        HTTPException(429): Rate limit exceeded

    Example:
        >>> POST /api/auth/change-password
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> {"old_password": "oldpass123", "new_password": "newpass123"}
        >>> Response: {"message": "Password changed successfully"}
    """
    # Verify old password
    if not verify_password(body.old_password, user.password_hash):
        raise AuthenticationError("Invalid current password")

    # Hash new password
    new_password_hash = hash_password(body.new_password)

    # Update password in database
    repo = UserRepository(db)
    await repo.update_password(user.id, new_password_hash)
    await db.commit()

    return {"message": "Password changed successfully"}
