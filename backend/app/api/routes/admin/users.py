"""
Admin User Management API Endpoints

Admin-only endpoints for user CRUD operations.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.db.repositories.user_repo import UserRepository
from app.schemas.admin import UserItem, UserListResponse

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/admin/users", tags=["admin", "users"])


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
