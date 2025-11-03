"""
Dependency Injection

FastAPI dependencies for database sessions, authentication, and other services.
These dependencies will be used throughout the application via Depends().
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError
from app.db.models import User
from app.db.session import get_db
from app.services.auth_service import AuthService


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authentication dependency - validates session and returns current user.

    Extracts Bearer token from Authorization header, validates session,
    and returns the authenticated user. Use with Depends() in protected endpoints.

    Args:
        request: FastAPI request (contains Authorization header)
        db: Database session

    Returns:
        User: Authenticated user object

    Raises:
        AuthenticationError: Missing Authorization header
        AuthenticationError: Invalid Authorization header format
        AuthenticationError: Invalid or expired session token
        AuthenticationError: User not found (deleted after session created)

    Example:
        >>> @app.get("/protected")
        >>> async def protected_route(user: User = Depends(get_current_user)):
        >>>     return {"message": f"Hello {user.email}"}
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise AuthenticationError("Not authenticated")

    # Parse Bearer token
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise AuthenticationError("Invalid authentication credentials")

    # Validate session and get user
    auth_service = AuthService(db)
    user = await auth_service.validate_session(token)

    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Admin-only authentication dependency.

    Requires user to be authenticated AND have role='admin'.
    Use with Depends() in admin-protected endpoints.

    Args:
        user: Authenticated user from get_current_user

    Returns:
        User: Admin user object

    Raises:
        HTTPException: 403 Forbidden if user.role != 'admin'

    Example:
        >>> @router.post("/admin/channels")
        >>> async def create_channel(user: User = Depends(get_admin_user)):
        >>>     # Only admins can access this
        >>>     pass
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
