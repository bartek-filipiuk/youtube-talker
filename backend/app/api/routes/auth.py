"""
Authentication API Endpoints

Provides REST endpoints for user registration, login, logout, and session validation.
Rate limiting applied to prevent abuse.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Register new user account.

    Rate limit: 5 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        body: Registration data (email, password)
        db: Database session

    Returns:
        UserResponse with user info (id, email, created_at)

    Raises:
        HTTPException(409): Email already registered
        HTTPException(422): Invalid email or password too short
        HTTPException(429): Rate limit exceeded

    Example:
        >>> POST /api/auth/register
        >>> {"email": "user@example.com", "password": "securepass123"}
        >>> Response: {"id": "...", "email": "user@example.com", "created_at": "..."}
    """
    auth_service = AuthService(db)
    user = await auth_service.register_user(body.email, body.password)
    return UserResponse.model_validate(user)


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
        HTTPException(401): No Authorization header provided

    Example:
        >>> POST /api/auth/logout
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Parse Bearer token
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format. Use: Bearer <token>"
        )

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
