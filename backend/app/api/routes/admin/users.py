"""
Admin User Management API Endpoints

Admin-only endpoints for user CRUD operations.
"""

import secrets
import string
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.security import hash_password
from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.db.repositories.user_repo import UserRepository
from app.schemas.admin import UserItem, UserListResponse

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/admin/users", tags=["admin", "users"])


# ============================================================================
# Schemas
# ============================================================================


class CreateUserRequest(BaseModel):
    """Create user request schema"""
    email: EmailStr


class CreateUserResponse(BaseModel):
    """Create user response with generated password"""
    user: UserItem
    generated_password: str


# ============================================================================
# Helper Functions
# ============================================================================


def generate_random_password(length: int = 16) -> str:
    """
    Generate a cryptographically secure random password.

    Guarantees at least one character from each required class:
    uppercase, lowercase, digit, and symbol.

    Args:
        length: Password length (default: 16 characters, minimum 4)

    Returns:
        Random password with guaranteed mixed case, digits, and symbols

    Raises:
        ValueError: If length is less than 4
    """
    if length < 4:
        raise ValueError("Password length must be at least 4 characters")

    # Define character pools
    symbols = string.punctuation.replace(' ', '')
    pool = string.ascii_letters + string.digits + symbols

    # Ensure at least one character from each required class
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(symbols),
    ]

    # Fill remaining positions with random characters from full pool
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]

    # Combine and shuffle to avoid predictable pattern
    password_chars = required + remaining
    secrets.SystemRandom().shuffle(password_chars)

    return ''.join(password_chars)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_user(
    request: Request,
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> CreateUserResponse:
    """
    Create new user with auto-generated password (admin only).

    Generates a secure random password and returns it ONCE in the response.
    Admin must save and share this password with the user.

    Rate limit: 20/minute

    Args:
        request: FastAPI request (for rate limiting)
        body: User creation data (email only)
        db: Database session
        admin: Authenticated admin user

    Returns:
        CreateUserResponse with user info and generated password

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 409: Email already registered

    Example:
        >>> POST /api/admin/users
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Body: {"email": "newuser@example.com"}
        >>> Response: {
        >>>   "user": {"id": "...", "email": "newuser@example.com", ...},
        >>>   "generated_password": "xY9#mK2$pL7..."
        >>> }
    """
    repo = UserRepository(db)

    try:
        # Check if email already exists
        existing_user = await repo.get_by_email(body.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )

        # Generate secure random password
        password = generate_random_password()
        password_hash = hash_password(password)

        # Create user
        user = await repo.create(email=body.email, password_hash=password_hash)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Admin {admin.id} created user {user.id} ({body.email})")

        return CreateUserResponse(
            user=UserItem(
                id=user.id,
                email=user.email,
                role=user.role,
                transcript_count=user.transcript_count,
                created_at=user.created_at,
            ),
            generated_password=password
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}",
        ) from e


@router.get("", response_model=UserListResponse)
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> UserListResponse:
    """
    List all users with pagination (admin only).

    Returns all users ordered by created_at DESC (newest first).
    Includes email, role, transcript count, and creation date.

    Rate limit: 60/minute

    Args:
        request: FastAPI request (for rate limiting)
        limit: Maximum users to return (1-100, default 50)
        offset: Number of users to skip (default 0)
        db: Database session
        admin: Authenticated admin user

    Returns:
        UserListResponse: Paginated list of users

    Raises:
        HTTPException 403: Non-admin access

    Example:
        >>> GET /api/admin/users?limit=20&offset=0
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Response: {
        >>>   "users": [
        >>>     {
        >>>       "id": "...",
        >>>       "email": "user@example.com",
        >>>       "role": "user",
        >>>       "transcript_count": 5,
        >>>       "created_at": "2025-01-15T10:30:00Z"
        >>>     }
        >>>   ],
        >>>   "total": 42,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """
    repo = UserRepository(db)

    try:
        users, total = await repo.list_all_users(limit=limit, offset=offset)

        # Convert to response schema
        user_items: List[UserItem] = [
            UserItem(
                id=user.id,
                email=user.email,
                role=user.role,
                transcript_count=user.transcript_count,
                created_at=user.created_at,
            )
            for user in users
        ]

        logger.info(
            f"Admin {admin.id} listed {len(user_items)} users "
            f"(limit={limit}, offset={offset}, total={total})"
        )

        return UserListResponse(
            users=user_items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}",
        ) from e


@router.post("/{user_id}/reset-password", response_model=CreateUserResponse)
@limiter.limit("10/minute")
async def reset_user_password(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> CreateUserResponse:
    """
    Reset user password with auto-generated password (admin only).

    Generates a new secure random password and returns it ONCE in the response.
    Admin must save and share this password with the user.
    Cannot reset your own password for security.

    Rate limit: 10/minute

    Args:
        request: FastAPI request (for rate limiting)
        user_id: UUID of user whose password to reset
        db: Database session
        admin: Authenticated admin user

    Returns:
        CreateUserResponse with user info and generated password

    Raises:
        HTTPException 400: Trying to reset own password
        HTTPException 403: Non-admin access
        HTTPException 404: User not found

    Example:
        >>> POST /api/admin/users/550e8400-e29b-41d4-a716-446655440000/reset-password
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Response: {
        >>>   "user": {"id": "...", "email": "user@example.com", ...},
        >>>   "generated_password": "xY9#mK2$pL7..."
        >>> }
    """
    repo = UserRepository(db)

    # Prevent admin from resetting their own password
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reset your own password. Use the change password feature instead."
        )

    try:
        # Get user to verify existence
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )

        # Generate secure random password
        password = generate_random_password()
        password_hash = hash_password(password)

        # Update password
        await repo.update_password(user_id, password_hash)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Admin {admin.id} ({admin.email}) reset password for user {user.id} ({user.email})")

        return CreateUserResponse(
            user=UserItem(
                id=user.id,
                email=user.email,
                role=user.role,
                transcript_count=user.transcript_count,
                created_at=user.created_at,
            ),
            generated_password=password
        )

    except HTTPException:
        raise
    except ValueError as e:
        # User not found from update_password
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to reset password for user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}",
        ) from e


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> None:
    """
    Delete user and all related data (admin only).

    Hard delete operation. Removes:
    - User account
    - All sessions
    - All conversations and messages
    - All channel conversations and messages
    - All transcripts and chunks

    Cannot delete yourself (current admin).

    Rate limit: 20/minute

    Args:
        request: FastAPI request (for rate limiting)
        user_id: UUID of user to delete
        db: Database session
        admin: Authenticated admin user

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException 400: Trying to delete yourself
        HTTPException 403: Non-admin access
        HTTPException 404: User not found

    Example:
        >>> DELETE /api/admin/users/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Response: 204 No Content
    """
    repo = UserRepository(db)

    # Prevent admin from deleting themselves
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    try:
        # Delete user and all related data
        await repo.delete_user(user_id)
        await db.commit()

        logger.info(f"Admin {admin.id} deleted user {user_id}")
    except ValueError as e:
        # User not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}",
        ) from e
