"""
Admin Settings API Endpoints

Admin-only endpoints for managing system-wide settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.db.repositories.config_repo import ConfigRepository


# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/admin/settings", tags=["admin", "settings"])


# ============================================================================
# Schemas
# ============================================================================


class RegistrationStatusResponse(BaseModel):
    """Registration status response"""
    enabled: bool


class RegistrationStatusRequest(BaseModel):
    """Registration status toggle request"""
    enabled: bool


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/registration", response_model=RegistrationStatusResponse)
@limiter.limit("60/minute")
async def get_registration_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> RegistrationStatusResponse:
    """
    Get current registration status (admin only).

    Returns whether new user registrations are currently allowed.

    Rate limit: 60/minute

    Args:
        request: FastAPI request (for rate limiting)
        db: Database session
        admin: Authenticated admin user

    Returns:
        RegistrationStatusResponse: Current registration status

    Raises:
        HTTPException 403: Non-admin access

    Example:
        >>> GET /api/admin/settings/registration
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Response: {"enabled": true}
    """
    repo = ConfigRepository(db)

    try:
        config = await repo.get_value("registration_enabled")

        # Default to enabled if config doesn't exist
        enabled = config.get("enabled", True) if config else True

        logger.info(f"Admin {admin.id} checked registration status: {enabled}")

        return RegistrationStatusResponse(enabled=enabled)

    except Exception as e:
        logger.error(f"Failed to get registration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get registration status: {str(e)}",
        ) from e


@router.post("/registration", response_model=RegistrationStatusResponse)
@limiter.limit("20/minute")
async def set_registration_status(
    request: Request,
    body: RegistrationStatusRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> RegistrationStatusResponse:
    """
    Toggle user registration on/off (admin only).

    Controls whether new users can register accounts.
    Existing users can always login regardless of this setting.

    Rate limit: 20/minute

    Args:
        request: FastAPI request (for rate limiting)
        body: Registration status to set
        db: Database session
        admin: Authenticated admin user

    Returns:
        RegistrationStatusResponse: Updated registration status

    Raises:
        HTTPException 403: Non-admin access

    Example:
        >>> POST /api/admin/settings/registration
        >>> Headers: {"Authorization": "Bearer <admin_token>"}
        >>> Body: {"enabled": false}
        >>> Response: {"enabled": false}
    """
    repo = ConfigRepository(db)

    try:
        await repo.set_value(
            key="registration_enabled",
            value={"enabled": body.enabled},
            description="Allow new user registrations"
        )
        await db.commit()

        logger.info(
            f"Admin {admin.id} {'enabled' if body.enabled else 'disabled'} user registration"
        )

        return RegistrationStatusResponse(enabled=body.enabled)

    except Exception as e:
        logger.error(f"Failed to set registration status: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set registration status: {str(e)}",
        ) from e
